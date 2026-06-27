---
name: iris-gateway
description: Iris Gateway를 통한 KakaoTalk 모든 채팅방 조회, 전송, 자동 모니터링 통합 스킬
tags: [iris, kakao, monitoring, query]
---

# Iris Gateway Skill

## Purpose
Iris Gateway(Iris)를 통해 **KakaoTalk의 모든 채팅방**에 접근하는 통합 스킬입니다.

주요 기능:
- 임의 채팅방 메시지 조회 (`/query`)
- 메시지 전송 (`/reply`)
- 수동 복호화 (`/decrypt`)
- 설정 관리
- **자동 방 모니터링** (새 메시지 감지 + 키워드 필터링)

## Iris base URL
Hermes Iris 플랫폼 설정 또는 환경변수를 사용합니다.

우선순위:
1. `IRIS_BASE_URL` (예: `http://192.168.0.10:3000`)
2. `IRIS_HOST` + `IRIS_PORT` (예: `127.0.0.1` + `3000`)

플러그인이 활성화되어 있으면 gateway의 `platforms.iris.extra.host` / `port`도 동일하게 사용할 수 있습니다.

## Core Principles
- `chat_id`를 기준으로 방을 구분합니다.
- 모든 SQL 조회는 `/query`를 통해 수행하며, 암호화 필드는 자동 복호화됩니다.
- Hermes gateway는 Iris **`/ws` WebSocket**으로 실시간 인바운드를 수신합니다 (HTTP webhook 아님).
- WS 수신 후 adapter가 enrich(장문·미디어·답장·아바타)하고, `allowed_chat_ids` 통과 시 에이전트로 전달합니다.
- 모니터링·과거 조회는 **Polling** (`/query`)을 사용합니다.

---

## Gateway adapter 인바운드 (Hermes WS)

코드: `plugins/platforms/iris/adapter.py`, `kakao_payload.py`, `participant.py`

### 처리 순서
```
Iris /ws 수신
  → JSON 파싱 (비동기 task — WS recv 루프 블로킹 방지)
  → _build_message_event (장문 CDN·미디어 캐시·답장 맥락·발신자 enrich)
  → _should_ignore_inbound
  → allowed_chat_ids (+ optional user_id 필터)
  → handle_message → 에이전트
```

### 인바운드 무시 조건 (adapter)
| 조건 | 판별 | 비고 |
|------|------|------|
| 봇/본인 발신 | `v.origin == "WRITE"` | `should_skip_self_by_v_origin()` — **bot_id/name 비교 안 함** |
| 시스템 피드 | `message`가 `{"feedType"...}` 또는 `type==0` | `is_system_feed_message()` |
| 미등록 방 | `chat_id ∉ allowed_chat_ids` | `!cr`/`!adcr`만 예외 처리 |
| user_id 필터 | `IRIS_USER_ID_FILTER=true`이고 user 미등록 | chat_id 필터와 **AND** |

`SYNCMSG`/`MCHATLOGS`는 Iris Android observer가 WS emit 전에 제외합니다.

### bot_id 자동 조회
- `IRIS_BOT_ID` / `config.extra.bot_id` 미설정 시 **`connect()` 및 발신자 enrich 전** `GET /config`로 `bot_id`·`bot_name` 자동 설정
- 용도: `/decrypt`의 `user_id`, 오픈챗 봇 계정 `member_type` 조회 — **루프 방지에는 사용하지 않음**

### 발신자 enrich (`event.extra`)
- `ensure_message_event_extra()`로 `extra` dict 보장 (프로덕션 `MessageEvent`에 필드 없을 수 있음)
- **오픈챗 멤버** (`user_id` ≥ 10,000,000,000): `open_chat_member` 조회 → `HOST`/`MANAGER`/`NORMAL`
- **봇 계정** (`user_id == bot_id`): `open_profile` 조회 → `BOT`
- **일반 카톡 유저** (`user_id` < 10,000,000,000): 역할 없음 — `sender_member_type` **생략**
- 아바타: 실프로필은 방 프로필, 오픈챗 멤버는 `open_chat_member` URL → 로컬 캐시 경로

---

## Action Catalog (액션 목록)

| 분류 | 액션 | 방법 | 비고 |
|------|------|------|------|
| 조회 | 최근 메시지 | `POST /query` | `chat_logs` + `bind` |
| 조회 | 방 목록 | `POST /query` | `GROUP BY chat_id` |
| 조회 | 유저별 메시지 | `POST /query` | `user_id` 필터 |
| 조회 | 답장 원문 | `POST /query` | `src_logId` → `chat_logs.id` |
| 조회 | 방 메타 | `POST /query` | `chat_rooms`, `link_id` |
| 전송 | 텍스트 | `POST /reply` | `type: text` |
| 전송 | 이미지 1장 | `POST /reply` | `type: image`, Base64 |
| 전송 | 이미지 여러 장 | `POST /reply` | `type: image_multiple`, Base64[] |
| 전송 | 스레드 답장 | `POST /reply` | `threadId` 필드 추가 |
| 복호화 | 수동 복호화 | `POST /decrypt` | `user_id` = `bot_id` |
| 설정 | 봇 ID 확인 | `GET /config` | `bot_id` 추출 |
| 설정 | AOT 토큰 | `GET /aot` | 리액션 등 고급 API용 |
| 관리 | 방 등록 | `!adcr` | `allowed_chat_ids`에 추가 |
| 관리 | chat_id 확인 | `!cr` | 현재 방 ID 응답 |
| 모니터링 | 키워드 감지 | cron + `/query` | `monitored_rooms.json` |

---

## 1. 메시지 조회 (`/query`)

**엔드포인트**: `POST {IRIS_BASE}/query`

### 기본 요청 형식
```json
{
  "query": "SQL 문자열",
  "bind": ["값1", "값2"]
}
```

### 자주 사용하는 쿼리 패턴

#### (1) 특정 방 최근 메시지
```sql
SELECT _id, chat_id, user_id, message, attachment, type, created_at, v
FROM chat_logs 
WHERE chat_id = ? 
ORDER BY _id DESC 
LIMIT ?
```

#### (2) 전체 방 목록 + 메시지 수
```sql
SELECT chat_id, COUNT(*) as msg_count, MAX(_id) as last_id 
FROM chat_logs 
GROUP BY chat_id 
ORDER BY last_id DESC 
LIMIT 30
```

#### (3) 특정 유저 메시지 (모든 방)
```sql
SELECT chat_id, message, created_at 
FROM chat_logs 
WHERE user_id = ? 
ORDER BY _id DESC 
LIMIT 20
```

#### (4) 답장(인용) 원문 조회
```sql
SELECT _id, message, attachment, type, user_id, v
FROM chat_logs
WHERE id = ?
```

#### (5) 키워드 검색 (모니터링)
```sql
SELECT _id, chat_id, user_id, message, created_at
FROM chat_logs
WHERE chat_id = ? AND message LIKE ?
ORDER BY _id DESC
LIMIT 20
```

#### (6) 오픈채팅 link_id (리액션 등)
```sql
SELECT link_id FROM chat_rooms WHERE id = ?
```

### 조회 액션 대응 방안

| 상황 | 대응 |
|------|------|
| `message`가 잘림 | `attachment` JSON 확인 → `path` 있으면 장문 CDN (아래 §6) |
| 이름이 Base64 | `v` 컬럼의 `enc` + `/decrypt` (`user_id` = `bot_id`) |
| `attachment`만 있고 `message` 비어 있음 | `type`으로 미디어 종류 판별 (§5 참고) |
| 벌크 조회 필요 | `{"queries": [{...}, {...}]}` 형식 사용 |

---

## 2. 메시지 전송 (`/reply`)

**엔드포인트**: `POST {IRIS_BASE}/reply`

### 텍스트
```json
{
  "type": "text",
  "room": "chat_id",
  "data": "메시지 내용"
}
```

### 이미지 (단일)
```json
{
  "type": "image",
  "room": "chat_id",
  "data": "Base64..."
}
```

### 이미지 (다중)
```json
{
  "type": "image_multiple",
  "room": "chat_id",
  "data": ["Base641", "Base642"]
}
```

### 스레드(답장) 전송
```json
{
  "type": "text",
  "room": "chat_id",
  "data": "답장 내용",
  "threadId": "원본_log_id"
}
```

### 전송 액션 대응 방안

| 요청 | 대응 | 제한 |
|------|------|------|
| 긴 텍스트 전송 | 4000자 단위 분할 전송 | Hermes adapter 자동 truncate |
| 이미지 + 설명 | image 전송 후 text follow-up | caption 별도 메시지 |
| 파일(PDF 등) 전송 | **불가** — 파일명+안내 텍스트로 대체 | Iris API 미지원 |
| 텍스트 파일 전송 | 12KB 이하면 내용 인라인, 초과 시 파일명만 | `MAX_INLINE_TEXT_BYTES` |
| 진행 상황 업데이트 | 동일 내용 중복 전송 억제 | `edit_message` dedupe |
| 여러 이미지 | `image_multiple` 우선, 1장이면 `image` | Base64 인코딩 필수 |

---

## 3. 수동 복호화 (`/decrypt`)

```json
{
  "enc": 0,
  "b64_ciphertext": "...",
  "user_id": 1234567890
}
```

**규칙**: `user_id`는 반드시 `GET /config`의 `bot_id`를 사용합니다.

| 결과 | 대응 |
|------|------|
| `plain_text` 반환 | 그대로 사용 |
| 실패 / 빈 값 | `알 수 없음` 표시, 가명(A/B/C) 부여 검토 |
| 닉네임 필드 | `open_chat_member`, `friends` 테이블 + `enc` 조합 |

---

## 4. 설정 관리

| 엔드포인트 | 설명 |
|------------|------|
| `GET /config` | 현재 설정 조회 (`bot_id` 포함) |
| `GET /aot` | AOT 토큰 (카카오 리액션 API용) |
| `POST /config/dbrate` | DB 폴링 주기 |
| `POST /config/sendrate` | 전송 간격 |
| `POST /config/endpoint` | Webhook 설정 |
| `GET /dashboard` | 웹 UI |

### 환경변수 (Hermes 플러그인)

| 변수 | 용도 |
|------|------|
| `IRIS_HOST` / `IRIS_PORT` / `IRIS_BASE_URL` | Iris HTTP·WS 대상 |
| `IRIS_ALLOWED_CHAT_IDS` | 에이전트 응답 허용 방 (비우면 전체 무제한) |
| `IRIS_USER_ID_FILTER` | `true`면 user_id 화이트리스트 AND 적용 (기본 off) |
| `IRIS_ALLOWED_USER_IDS` | user_id 필터 목록 (쉼표 구분) |
| `IRIS_ALLOW_ALL_USERS` | gateway 사용자 인가 우회 (`IRIS_ALLOW_ALL_USERS=true`) |
| `IRIS_BOT_ID` | botId (미설정 시 `GET /config` 자동 조회) — 복호화·역할 조회용 |
| `IRIS_CHECK_REACTION` | 수신 시 ✅ 리액션 (기본 off) |
| `IRIS_AUTO_SKILLS` | 자동 로드 스킬 (기본 `iris-chat-assistant`) |
| `IRIS_TALK_VERSION` | 카카오 talk-agent 버전 (리액션 API) |

**루프 방지**는 env가 아니라 WS payload의 **`v.origin=WRITE`** 로 처리합니다.

---

## 5. 카카오 메시지 타입 참조 (인바운드)

Hermes Iris adapter가 인식하는 타입:

| type | 종류 | adapter 처리 |
|------|------|-------------|
| 1 | 텍스트 | 본문 사용, 3900자+ 시 CDN 전문 fetch |
| 2 | 단일 사진 | `url`/`path` → 이미지 캐시 |
| 26 | 답장 | `src_logId`로 원문 조회 + 인용 미디어 캐시 |
| 27 | 다중 사진 | `imageUrls[]` |
| 71 | 앨범 | `C.THL[].TH.THU` |
| 18 | 파일 | DOCUMENT, CDN 다운로드 시도 |
| 3, 36 | 동영상 | VIDEO, URL 캐시 |
| 5, 16 | 음성 | VOICE, URL 캐시 |
| 0 / feed | 시스템 피드 | **무시** (`feedType` JSON) |

타입은 `16384` 이상이면 `type % 16384`로 정규화합니다.

---

## 6. 장문 텍스트 (3900자 이상)

카카오는 긴 텍스트를 WS/DB preview로 일부만 보내고, 전문은 CDN에 둡니다.

**조건**: `len(message) >= 3900` AND `attachment.path` 존재 AND `type == 1`

**전문 URL**: `https://dn-m.talk.kakao.com/{attachment.path}`

### 대응 방안

| 상황 | 액션 |
|------|------|
| Gateway WS 수신 | adapter가 자동 fetch → `event.text`에 전문 반영 |
| `/query`로 직접 조회 | preview만 보이면 `attachment.path`로 CDN GET |
| fetch 실패 | preview 유지 + 사용자에게 "전문 일부만 확인됨" 안내 |
| 요약/분석 요청 | 반드시 3900자 이상이면 CDN 전문 확인 후 처리 |

---

## 7. 방 등록 명령어

| 명령 | 동작 | 허용 범위 |
|------|------|----------|
| `!cr` | 현재 `chat_id` 텍스트로 응답 | 모든 방 |
| `!adcr` | `allowed_chat_ids`에 방 자동 등록 | 모든 방 |

등록되지 않은 방에서는 에이전트 응답이 **비활성**입니다 (`!cr`/`!adcr`만 동작).

---

## 8. 자동 방 모니터링

모니터링 상태 파일: `~/.hermes/skills/iris-gateway/monitored_rooms.json`

### 모니터링 액션 흐름
1. `monitored_rooms.json`에서 감시 대상 `chat_id` + `last_id` 로드
2. `/query`로 `last_id` 이후 새 메시지 조회
3. 키워드 매칭 시 알림 전송 (`/reply` 또는 Hermes cron)
4. `last_id` 갱신 후 저장

Hermes cron 예시:
```bash
hermes cron create --schedule "*/15 * * * * *" --prompt "iris-gateway 모니터링" --skills iris-gateway
```

### 모니터링 대응 방안

| 트리거 | 대응 |
|--------|------|
| 키워드 매칭 | 해당 방에 요약 알림 전송 |
| 이미지 포함 | `attachment` 파싱 → 필요 시 별도 vision 분석 |
| 장문 메시지 | CDN 전문 fetch 후 키워드 재검사 |
| 시스템 피드 | 스킵 (입퇴장·강퇴 등) |

---

## 9. 오류·제한 대응 (공통)

| 문제 | 원인 | 대응 |
|------|------|------|
| `/reply` 4xx/5xx | 방 ID 오류, Iris 미실행 | `GET /config`로 연결 확인 |
| 이미지 전송 실패 | Base64 오류, 용량 초과 | 파일 재인코딩, 해상도 축소 |
| 미디어 다운로드 실패 | CDN 만료/네트워크 | `[첨부 다운로드 실패 — URL: ...]` 참고 |
| 복호화 실패 | enc 불일치, bot_id 오류 | `GET /config`로 `bot_id` 확인 (자동 조회 실패 시 수동 설정) |
| 무한 루프 | `v.origin` 누락·오류 | adapter는 `WRITE`만 무시; `v` 없는 row는 에이전트까지 갈 수 있음 |
| WS 수신 없음 | Iris observer 정체·프로세스 다운 | `GET /dashboard/status` 확인 후 Iris 재시작, gateway restart |
| `event.extra` 오류 | 구형 MessageEvent | adapter `ensure_message_event_extra()` 처리 (최신 플러그인) |
| 파일 전송 요청 | API 미지원 | 파일명+내용 요약 텍스트로 대체 안내 |

## 10. 비서 톤 (에이전트 응답)

Iris 대화의 응답 스타일은 **`iris-chat-assistant` 스킬**의 "비서 톤 & 응답 가이드"를 따릅니다.
요약: 정중한 해요체, 핵심→부연→(선택)다음 제안, 카톡 순수 텍스트, 한 줄 "네." 회피.

---

이 스킬로 Iris Gateway의 **조회·전송·타입별 처리·모니터링**을 처리합니다.