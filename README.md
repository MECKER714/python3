# 🎄 ASCII Christmas Tree

link: https://mecker714.github.io/python3/

파이썬 표준 라이브러리만으로 만든 3D 아스키 크리스마스 트리입니다.
터미널에서도 돌고, GitHub Pages에서는 같은 `tree.py`가 브라우저(Pyodide)에서 그대로 실행됩니다.

## 터미널에서 실행

```bash
python3 tree.py      # 종료: Ctrl+C
```

- 터미널 크기 80x26 이상, 256색 지원 터미널 권장
- 문구/이름표는 `tree.py` 맨 위의 `MESSAGE`, `TAG` 변수에서 바꿉니다.

## 타임라인

| 시간 | 내용 |
| --- | --- |
| 0초 | 트리 회전, 눈 내림 |
| 0~3초 | 금색 전구 줄, 빨강·파랑·분홍 꼬마전구, 꼭대기 별이 아래부터 차례로 달림 |
| 5초 | 산타 썰매가 지나가며 선물 5개를 떨어뜨림 (바닥에서 통통 튐) |
| 12초 | 가장 큰 상자에 `직원` 이름표가 달리고, 열리면서 `MESSAGE`가 한 글자씩 나옴 |

## GitHub Pages 배포

1. 저장소에 `index.html`, `tree.py`, `README.md`를 올립니다. (같은 폴더, 루트 권장)
2. 저장소 **Settings → Pages → Build and deployment**
   - Source: `Deploy from a branch`
   - Branch: `main` / `/ (root)` → Save
3. 잠시 후 `https://<사용자명>.github.io/<저장소명>/` 에서 확인합니다.

처음 열 때 Pyodide(약 10MB)를 내려받아서 몇 초 걸리고, 이후에는 브라우저 캐시를 씁니다.

### 로컬에서 웹 버전 확인

`index.html`이 `tree.py`를 fetch 하므로 `file://`로는 안 열립니다.

```bash
python3 -m http.server 8000
# http://localhost:8000
```

## 구성

- `tree.py` : 렌더링 로직 전부. 터미널 실행(`main`)과 웹용 `render_frame(t, cols, rows)`를 함께 제공
- `index.html` : xterm.js + Pyodide로 `render_frame`을 20fps로 호출
