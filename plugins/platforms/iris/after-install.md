# Iris 플러그인 설치 완료

## 다음 단계

1. **의존성** (WS 수신):
   ```bash
   pip install websockets
   ```

2. **Iris 연결 설정**:
   ```bash
   hermes setup iris
   ```
   또는 `~/.hermes/config.yaml`에 `gateway.platforms.iris` 추가  
   (예시: 저장소의 `config/iris.example.yaml`)

3. **게이트웨이 실행**:
   ```bash
   hermes gateway run
   ```

4. **방 등록**: 카톡 방에서 `!cr`로 chat_id 확인 → `!adcr`로 자동 등록

## 환경 변수

| 변수 | 설명 |
|------|------|
| `IRIS_HOST` | Iris Android IP |
| `IRIS_PORT` | HTTP/WS 포트 (기본 3000) |
| `IRIS_ALLOWED_CHAT_IDS` | 응답할 chat_id (쉼표 구분) |

전체 목록: `plugin.yaml`