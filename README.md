# Hermes Iris (KakaoTalk) Platform Plugin

[Hermes Agent](https://github.com/NousResearch/hermes-agent)용 **카카오톡(Iris)** 게이트웨이 플러그인입니다.  
루팅된 Android 기기에서 동작하는 [Iris](https://github.com/dolidolih/Iris)와 WebSocket(`/ws`)·HTTP(`/reply`)로 연동합니다.

## 요구 사항

| 구성 요소 | 설명 |
|-----------|------|
| Hermes Agent | 게이트웨이 실행 환경 (`pip install hermes-agent` 등) |
| Iris | 루팅 Android + 카카오톡, HTTP/WS 서버 (기본 포트 3000) |
| Python 패키지 | `websockets` (실시간 수신), `httpx` (Hermes 기본 포함) |
| 네트워크 | Hermes 게이트웨이 → Iris 기기 IP:포트 접근 가능 |

## 빠른 설치 (권장)

```bash
# 1. Hermes Agent 설치 (미설치 시)
pip install hermes-agent

# 2. 플러그인 설치 (GitHub에서)
hermes plugins install entworacy/hermes-iris-kakaotalk/plugins/platforms/iris

# 3. WS 의존성
pip install websockets

# 4. 대화형 설정 (Iris IP·포트·허용 방)
hermes setup iris

# 5. 게이트웨이 시작
hermes gateway run
```

설치 스크립트를 쓰려면:

```bash
git clone https://github.com/entworacy/hermes-iris-kakaotalk.git
cd hermes-iris-kakaotalk
./scripts/install.sh
```

## 수동 설정

`~/.hermes/config.yaml` 예시 (`config/iris.example.yaml` 참고):

```yaml
plugins:
  enabled:
    - iris-platform   # hermes plugins install 후 키 이름

gateway:
  platforms:
    iris:
      enabled: true
      extra:
        host: "192.168.0.42"      # Iris Android IP
        port: 3000
        allowed_chat_ids:
          - "123456789012345"     # 응답할 chat_id
        talk_version: "26.1.0"
```

`bot_id`는 설정 파일에 넣지 않아도 됩니다. 미설정 시 Iris `GET /config`에서 자동 조회됩니다.

환경 변수로도 설정 가능합니다 (`IRIS_HOST`, `IRIS_PORT`, `IRIS_ALLOWED_CHAT_IDS` 등).  
자세한 목록은 `plugins/platforms/iris/plugin.yaml`을 참고하세요.

### 허용 채팅방 등록 (`!cr` / `!adcr`)

에이전트는 `allowed_chat_ids`에 등록된 방에서만 응답합니다.  
**등록되지 않은 방**에서는 아래 두 명령만 처리되고, 일반 메시지에는 응답하지 않습니다.

| 명령 | 동작 |
|------|------|
| `!cr` | 현재 방의 `chat_id`를 카톡으로 회신 |
| `!adcr` | 현재 방을 `allowed_chat_ids`에 추가하고 `~/.hermes/config.yaml`에 저장 |

#### 등록 절차

1. **게이트웨이 실행** — `hermes gateway run` (Iris WS 연결 상태 확인)
2. **등록할 카톡 방**에서 `!cr` 전송 → 봇이 `chat_id` 숫자를 돌려줌 (확인용)
3. 같은 방에서 `!adcr` 전송 → `등록 완료` 메시지와 함께 허용 목록에 추가됨
4. 이후 해당 방의 일반 메시지에 에이전트가 응답함

`!adcr`는 `gateway.platforms.iris.extra.allowed_chat_ids`에 방 ID를 쓰고,  
게이트웨이 재시작 없이 메모리에도 반영됩니다.

이미 등록된 방에서 `!adcr`를 다시내면 `이미 등록된 방입니다`라고 안내합니다.

#### 수동 등록 (선택)

`~/.hermes/config.yaml`에 직접 추가할 수도 있습니다.

```yaml
gateway:
  platforms:
    iris:
      extra:
        allowed_chat_ids:
          - "123456789012345"   # !cr로 확인한 chat_id
```

환경 변수: `IRIS_ALLOWED_CHAT_IDS=123456789012345,987654321098765` (쉼표 구분)

### 특정 사용자만 응답하기 (선택)

기본값은 **방(`chat_id`)만** 필터링하고, `user_id`는 모두 허용합니다.  
특정 사용자의 메시지에만 응답하려면 `user_id` 화이트리스트를 켭니다 (`chat_id` 필터와 **AND**).

```yaml
gateway:
  platforms:
    iris:
      extra:
        allowed_chat_ids:
          - "123456789012345"
        user_id_filter_enabled: true
        allowed_user_ids:
          - "987654321098765"   # 응답 허용할 user_id
```

환경 변수:

```bash
IRIS_USER_ID_FILTER=true
IRIS_ALLOWED_USER_IDS=987654321098765,111222333444555
```

`user_id_filter_enabled`가 `false`(기본)이면 `allowed_user_ids`는 무시됩니다.

## 개발 · 테스트

```bash
git clone https://github.com/entworacy/hermes-iris-kakaotalk.git
cd hermes-iris-kakaotalk

# 로컬 플러그인 연결
mkdir -p ~/.hermes/plugins/platforms
ln -sfn "$(pwd)/plugins/platforms/iris" ~/.hermes/plugins/platforms/iris

# config에 platforms/iris 또는 iris-platform 활성화 후
python3 -m pytest tests/gateway/ -q
```

## 번들 스킬

플러그인 로드 시 자동 설치됩니다 (`~/.hermes/skills/`):

- `iris-gateway` — 조회·전송·모니터링
- `iris-chat-assistant` — 자연어 액션·비서 톤 응답

## 라이선스

MIT — `LICENSE` 참고