# feroad-rest-api

Axum 기반 HTTP REST API 서버 보일러플레이트입니다.

## 요구 사항

- Rust 1.70+ (edition 2021)

## 실행

```bash
cp .env.example .env   # 선택 사항
cargo run
```

서버가 기동되면 다음 엔드포인트를 사용할 수 있습니다.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | 루트 헬스체크 |
| GET | `/api/v1/health` | 버전드 API 헬스체크 |

## 테스트

```bash
cargo test
```

## 환경 변수

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | 바인딩 호스트 |
| `PORT` | `3000` | 바인딩 포트 |
| `RUST_LOG` | `feroad_rest_api=debug,tower_http=debug` | 로그 필터 |

## 프로젝트 구조

```
src/
├── main.rs       # 엔트리포인트
├── lib.rs        # 라우터 생성 (테스트 재사용)
├── config.rs     # 환경 설정
├── error.rs      # API 에러 타입
└── routes/       # HTTP 라우트
```