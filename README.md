# Repo 를 분석 mp4 로 저장

Windows에서 FFmpeg 설치는 보통 압축본 다운로드 → 폴더 배치 → PATH 등록 → 버전 확인 순서로 하면 됩니다. FFmpeg 공식 사이트는 소스 코드만 직접 제공하고, Windows용 실행 파일은 공식 다운로드 페이지에서 연결하는 외부 빌드 배포처를 사용합니다.

1) FFmpeg 다운로드

가장 먼저 FFmpeg 공식 다운로드 페이지로 가세요. 공식 페이지에서 Windows용 사전 빌드 배포처 링크를 안내합니다.

권장 방식:

ffmpeg Windows build의 zip 압축본

보통 full 또는 essentials 계열 중 하나 선택

일반적으로는:

essentials: 기본 사용에 충분

full: 더 많은 코덱/기능 포함

2) 압축 해제

예를 들어 아래처럼 두면 관리가 편합니다.

C:\ffmpeg

압축을 풀면 보통 이런 구조가 보입니다.

C:\ffmpeg\bin\ffmpeg.exe
C:\ffmpeg\bin\ffprobe.exe
C:\ffmpeg\bin\ffplay.exe
3) 환경변수 PATH 등록

ffmpeg.exe가 들어 있는 bin 폴더를 PATH에 추가합니다.

추가할 경로 예시:

C:\ffmpeg\bin

설정 방법:

시작 메뉴에서 환경 변수 검색

시스템 환경 변수 편집

환경 변수

사용자 변수 또는 시스템 변수의 Path 선택

새로 만들기

C:\ffmpeg\bin 추가

확인 후 창 닫기

4) CMD 또는 PowerShell 다시 열기

이미 열려 있던 터미널은 PATH 변경을 반영하지 못할 수 있으니, 새로 열어야 합니다.

5) 설치 확인

아래 명령으로 확인합니다.

ffmpeg -version

정상 설치되면 버전 정보가 출력됩니다. FFmpeg는 공식 문서상 ffmpeg, ffplay, ffprobe 같은 명령행 도구를 제공합니다.


---

PowerShell 실행 정책 때문에 막힌 상태입니다. 가장 쉬운 해결은 아래 3가지 중 하나입니다.

방법 1. PowerShell에서 실행 정책 완화

현재 사용자 기준으로만 바꾸면 됩니다.

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

실행 후 Y 입력하고 다시 활성화합니다.

.\venv\Scripts\Activate.ps1

또는

venv\Scripts\Activate.ps1

정상이라면 프롬프트가 이렇게 바뀝니다.

(venv) PS C:\final-work>
방법 2. 현재 PowerShell 세션에서만 일시 허용

영구 변경이 부담되면, 지금 창에서만 허용할 수 있습니다.

Set-ExecutionPolicy -Scope Process Bypass

그 다음 바로:

.\venv\Scripts\Activate.ps1

이 방법은 현재 PowerShell 창을 닫으면 원래대로 돌아갑니다.

방법 3. CMD 방식으로 활성화

PowerShell 말고 CMD 방식 스크립트를 호출하면 더 단순할 때가 있습니다.

PowerShell 안에서 아래 실행:

cmd /k venv\Scripts\activate.bat

그러면 CMD 창이 열리면서 가상환경이 활성화됩니다.

지금 상황에서 가장 추천하는 순서
cd C:\final-work
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\venv\Scripts\Activate.ps1

그 다음 패키지 설치:

python -m pip install --upgrade pip
pip install pillow pyttsx3 markdown beautifulsoup4 pygments
추가 체크

가상환경이 실제로 만들어졌는지도 확인해보세요.

dir .\venv\Scripts\

정상이라면 보통 이런 파일들이 보입니다.

Activate.ps1

activate.bat

python.exe

pip.exe

아주 간단한 대안

PowerShell이 계속 번거로우면 아예 CMD에서 진행해도 됩니다.

cd C:\final-work
venv\Scripts\activate.bat
pip install pillow pyttsx3 markdown beautifulsoup4 pygments

원하시면 제가 다음 답변에서 PowerShell 기준으로 처음부터 venv 생성 → 활성화 → 패키지 설치까지 한 줄씩 그대로 복붙 가능한 전체 명령 세트로 정리해드리겠습니다.

---

```
cd C:\final-work
git clone https://github.com/edumgt/Java-Coin-Trade.git
python do.py --repo .\Java-Coin-Trade --out .\output_video
```