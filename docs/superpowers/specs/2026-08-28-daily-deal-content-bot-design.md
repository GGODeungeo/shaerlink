# 토스쇼핑 쉐어링크 — 하루특가 콘텐츠 생성 봇 (Phase 1) 설계

## 배경

최종 목표는 토스쇼핑 쉐어링크의 "하루특가"(30일 최저가) 상품을 매일 오후 6시에
쓰레드/틱톡/유튜브 3곳에 자동으로 링크·사진·사용법과 함께 올리는 개인 봇이다.

전체 계획은 4단계로 나뉜다:

1. **Phase 1 (이 문서의 범위)**: 콘텐츠 생성 툴. 채널·API 승인 없이 지금 바로 만들 수
   있는 부분만 구현한다. 사람이 결과물을 수동으로 각 플랫폼에 올린다.
2. Phase 2: 채널에 콘텐츠가 쌓인 뒤 Toss Sharelink Open API 신청/승인 → 스크래핑을
   공식 API 호출로 교체.
3. Phase 3: 플랫폼별 게시 API(Threads/TikTok/YouTube) 승인되는 대로 자동 포스팅 연결.
4. Phase 4: 스케줄러로 매일 18:00 트리거 연결.

Phase 2~4는 외부 심사 결과에 의존하므로 이번 스펙에는 포함하지 않는다.

## 목표 (Phase 1)

- 그날의 "하루특가"(30일 최저가 태그) 상품 전부를 스크래핑
- 상품별로 쉐어링크(제휴 링크) 발급
- 상품별로 쓰레드/틱톡/유튜브용 캡션 3종을 Claude API로 생성
- 상품 이미지·링크·캡션을 사람이 바로 복사해서 쓸 수 있는 폴더 구조로 저장

## 비목표

- 실제 SNS 포스팅 자동화 (Phase 3)
- Sharelink 공식 API 연동 (Phase 2)
- 스케줄링/크론 (Phase 4)
- 다중 계정, 다중 사용자 지원 (개인 봇 1인 전용)

## 아키텍처

```
main.py
  ├─ scrape.py   : Playwright로 하루특가(30일 최저가) 상품 목록 + 쉐어링크 수집 → products.json
  ├─ generate.py : products.json → Claude API로 캡션 3종 생성 → captions 병합
  └─ output/YYYY-MM-DD/NNN-상품명/{image.jpg, link.txt, captions.md} 저장
```

각 모듈은 `products.json` 스키마를 인터페이스로 공유한다 (실제 구현은 같은
프로세스 안에서 딕셔너리를 그대로 주고받고, `products.json`은 스키마를 고정하는
기록으로 파일에 남긴다). `scrape.py`의 출력 스키마만 고정해두면, Phase 2에서
`scrape.py`를 공식 API 호출로 교체해도 `generate.py`와 출력 구조는 그대로 재사용
가능하다.

## 컴포넌트

### scrape.py

- 입력: 없음 (고정 URL: `sharelink.toss.im/links/recommended-products?priceFilters=MIN_PRICE_30D`,
  로그인 세션은 Playwright의 저장된 브라우저 프로필을 재사용)
- 처리:
  1. 저장된 프로필로 브라우저 실행, 위 URL 접속
  2. 로그인 폼이 감지되면 즉시 에러 종료 (세션 만료 — 안내 메시지만 출력, 자동
     재로그인 시도 안 함)
  3. "하루특가" 목록에서 30일 최저가 태그가 붙은 상품만 파싱: 상품명, 판매가,
     할인율, 이미지 URL. 카테고리는 상품 조회 목록 화면에 상품별로 노출되지
     않으므로(사이드바 필터에만 존재) 수집하지 않음 — 캡션 생성은 상품명 기반으로
     대체
  4. 상품마다 "링크 발급" 클릭 → 발급된 쉐어링크 URL 수집
  5. 상품이 0개면 (사이트 구조 변경 등으로 파싱 실패 가능성) 에러로 중단 — 빈
     결과를 정상 종료로 취급하지 않음
- 출력: `output/YYYY-MM-DD/products.json`
  ```json
  [{"name": "...", "price": 12000, "discountRate": 61,
    "imageUrl": "...", "shareLink": "..."}]
  ```

### generate.py

- 입력: `products.json`
- 처리: 상품별로 Claude API 호출 1회, 상품명/가격/할인율을 프롬프트에 넣어
  쓰레드(캐주얼)/틱톡(후킹)/유튜브(설명형) 캡션 3종 생성
- 에러 처리: 개별 상품 호출 실패 시 해당 상품은 캡션 없이 건너뛰고 로그만 남김
  (파이프라인 전체를 중단시키지 않음)
- 출력: 상품별 `captions.md` (섹션: `## threads`, `## tiktok`, `## youtube`)

### main.py

- `scrape.py` → `generate.py` → 이미지 다운로드 및 폴더 정리를 순서대로 실행하는
  진입점. 스케줄링 없음 (수동 실행, Phase 4에서 cron 연결 예정).

### 출력 구조

```
output/2026-08-28/
  products.json
  001-상품명/
    image.jpg
    link.txt
    captions.md
  002-상품명/
    ...
```

## 에러 처리 정리

| 상황 | 동작 |
|---|---|
| 로그인 세션 만료 | 즉시 중단, 사람이 재로그인 후 세션 저장하라는 메시지 |
| 상품 0개 파싱 | 에러로 중단 (조용히 빈 결과 생성 안 함) |
| Claude API 개별 실패 | 해당 상품만 캡션 없이 스킵, 로그 기록, 전체는 계속 진행 |
| 이미지 다운로드 실패 | 해당 상품 폴더에 이미지 없이 링크/캡션만 저장, 로그 기록 |

## 테스트

- `scrape.py`: 저장해둔 샘플 HTML(픽스처)로 파싱 함수만 단위 테스트 — 실제 로그인
  없이 파싱 로직 검증
- `generate.py`: 프롬프트 응답이 `## threads` / `## tiktok` / `## youtube` 3섹션을
  모두 포함하는지 검증하는 간단한 assert 기반 테스트
- 전체 파이프라인: 실제 계정으로 1회 수동 실행 후 출력 폴더 구조 눈으로 확인 (E2E는
  자동화하지 않음 — 로그인 세션이 필요해 CI에서 돌릴 수 없음)

## 기술 스택

- Python + Playwright (동기 API)
- Anthropic Claude API (캡션 생성)
- 외부 프레임워크 없음, 표준 라이브러리 + `playwright`, `anthropic` 패키지만 사용
