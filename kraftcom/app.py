from flask import Flask, request, jsonify, render_template, make_response, redirect, session
from services.edit_service import update_user_info      # 사용자 정보 수정 서비스 함수
from services.user_service import register_user         # 회원가입 처리 함수
from services.auth_service import login_user            # 로그인 처리 함수
from services.auth_service import get_user_by_id        # 사용자 ID로 정보 조회
from pymongo import MongoClient                         # MongoDB와 연결하기 위한 클라이언트
import jwt                  # JWT 사용
from jwt import ExpiredSignatureError, InvalidTokenError        # JWT 예외 처리용
from datetime import datetime, timedelta        # 토큰 유효 시간 설정에  사용
import secrets      # 세션 키 등 보안용 랜덤 문자열 생성
import os       # OS 환경 변수 접근
from dotenv import load_dotenv      # .env 파일에서 환경 변수 로드


# .env 로드 및 환경 변수 설정
load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')        # JWT 서명을 위한 비밀키
MONGO_URI = os.getenv('MONGO_URI')          # MongoDB URI 주소
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')      # 사용할 MongoDB 데이터베이스 이름

app = Flask(__name__)
app.secret_key = SECRET_KEY

# MongoDB 클라이언트 연결 및 DB 생성
client = MongoClient('mongodb://abc1:abc1@54.180.249.140:27017')
db = client[MONGO_DB_NAME]

# DB 컬레션 참조 변수
users_collection = db['users']      # 사용자 정보 저장 컬렉션
crawlJobs_collection = db['crawl_jobs']     # 크롤링 잡 정보
posts_collection = db['posts']          # 게시글 정보 저장 컬렉션

PAGE = 20       # 페이징 처리를 위한 한 페이지 당 카드 수

# 회원 가입 페이지 반환
@app.route('/register', methods=['POST', 'GET'])
def register_page():
    if request.method == 'GET':
        return render_template('register.html')

    data = request.form.to_dict()
    required = ['name', 'id', 'password', 'email', 'season']        # 필수 항목만
    if not all(data.get(f) for f in required):
        return jsonify({'result': 'fail', 'message': '필수 항목을 모두 입력해주세요'}), 400

    result = register_user(data, users_collection, crawlJobs_collection)
    return redirect('./')

# 로그인 페이지 반환
@app.route('/login')
def login_page():
    return render_template('login.html')

# 회원가입 요청 처리
@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    data = request.form.to_dict()       # form 데이터를 딕셔너리로 변환
    required = ['name', 'id', 'password', 'email', 'season']        # 필수 입력 항목 목록

    # 모든 필수 항목이 입력되었는지 검증
    if not all(data.get(f) for f in required):
        return jsonify({'result': 'fail', 'message': '필수 항목을 모두 입력해주세요'}), 400

    # 사용자 등록 로직 호출
    result = register_user(data, users_collection, crawlJobs_collection)
    return redirect('./')

# # 로그인 요청 처리
# @app.route('/login', methods=['POST'])
# def login():
#     data = request.form.to_dict()
#     user_id = data.get('id')        # 아이디 추출
#     password = data.get('password')     # 비밀번호 추출

#     # 아이디 또는 비밀번호 하나라도 없으면 에러 발생
#     if not user_id or not password:
#         return "ID와 비밀번호를 입력해주세요.", 400

#     # 로그인 서비스 함수 호출
#     result = login_user(user_id, password, users_collection, SECRET_KEY)

#     if result['result'] == 'success':
#         user = get_user_by_id(user_id, users_collection)

#         session['user_id'] = user_id
#         session['profile_image'] = user.get('profile_image', 'default.png')  # None일 경우 default 처리

#         print(f"Session profile_image: {session['profile_image']}")  # 디버깅용 출력

#         response = make_response(redirect('/'))
#         token = result['token']

#         response.set_cookie(
#             'access_token',
#             token,
#             httponly=True,
#             samesite='Lax',
#             secure=True  # 배포 시 True로 변경 권장
#         )
#         return response
#     else:
#         return result['message'], 401


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.form.to_dict()
    user_id = data.get('id')
    password = data.get('password')

    if not user_id or not password:
        return "ID와 비밀번호를 입력해주세요.", 400     # ID 또는 PW가 비어 있을 경우 400 반환

    result = login_user(user_id, password, users_collection, SECRET_KEY)

    if result['result'] == 'success':
        response = make_response(redirect('/'))    # 로그인 성공 시 토큰 발급
        token = result['token']

        # 세션 쿠키로 설정(브라우저 종료 시 사라짐)
        response.set_cookie(
            'access_token',     # 쿠키 이름
            token,              # 토큰 값
            httponly = True,    # js에서 접근 불가
            samesite = 'LAX',   # CSRF 완화
            secure = False      # HTTPS에서만 쿠키 전송
        )
        return response
    else:
        return redirect('./')

# 토큰 인증 필요할 경우 사용 (마이 페이지 사용 시)
@app.route('/mypage')
def mypage():
    token = request.cookies.get('access_token')     # 브라우저 쿠키에 저장된 JWT 토큰을 가져와 token에 저장
    if not token:
        return redirect('/login')       # 토큰이 없을 경우 로그인 페이지로 리다이렉트

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])       # 토큰 복호화 시도
        user_id = payload['id']
        user = users_collection.find_one({'id': user_id})       # 토큰을 통해 사용자 ID 추출한 것은 DB에 조회

        if not user:
            return redirect('/login')       # ID는 유효하지만 DB에 사용자가 존재하지 않는 경우 다시 로그인 유도 (회원 탈퇴, 비활성화 경우 -> 계정은 삭제 되었지만 토큰은 유효할 수 있다.)

        return render_template('mypage.html', user=user)        # 인증 성공시 마이 페이지로 이동, 유저 객체를 템플릿에 넘겨 유저 정보 표시
    except jwt.ExpiredSignatureError:       # 토큰 만료시간이 지난 경우
        return redirect('/login')       # 재발급을 위해 로그인 리다이렉트
    except jwt.InvalidTokenError:       # 토큰이 위조 되었거나 구조가 잘못된 경우
        return redirect('/login')       # 로그인 리다이텍트

# 로그아웃
@app.route('/logout')
def logout():
    response = make_response(redirect('/'))    # /logout에 접근했을 때, 서버가 login 페이지로 이동
    response.set_cookie('access_token', '', max_age=0)  # 쿠키 삭제 : set_cookie는 쿠키를 설정하는 함수지만, value는 빈 문자열, max_age = 0(만료시간 0초라는 의미)을 함께 지정하면 쿠키 삭제 의미
    return response

# 카드 목록 전체 불러오기 (메인 페이지)
CARDS = list(posts_collection.find())

def slice_page(cursor: int):
    subset = [c for c in CARDS if c["_id"] < cursor] if cursor else CARDS   # 커서가 있다면 이후 항목만 추출
    subset = subset[: PAGE + 1]         # 다음 페이지 유무 확인용
    next_cur = subset[-1]["_id"] if len(subset) > PAGE else None    # 다음 커서 설정
    return subset[:PAGE], next_cur

@app.route("/")
def home():
    token = request.cookies.get('access_token')
    user_id = None
    profile_image = 'default.png'  # 기본값

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('id')

            # 사용자 조회
            user = db.users.find_one({'id': user_id})
            if user:
                print("user found:", user)
                if user.get('profile_image'):
                    profile_image = user['profile_image']
        except ExpiredSignatureError:
            print("token expired")
        except InvalidTokenError:
            print("invalid token")

    print("user_id from token:", user_id)
    print("profile_image:", profile_image)

    cards, next_cursor = slice_page(cursor=0)       # 카드 데이터 페이징
    print("cards loaded:", len(cards))
    print("next_cursor:", next_cursor)

    return render_template(
        "home.html",
        cards=cards,
        next_cursor=next_cursor,
        user_id=user_id,
        profile_image=profile_image
    )

# 카드 데이터만 AJAX로 로드할 떄 사용되는 API
@app.route("/api/cards")
def api_cards():
    cursor = int(request.args.get("cursor", 0))     # 요청 커서 값
    cards, next_cursor = slice_page(cursor)
    html = render_template("_card_frag.html", cards=cards)      # 카드 프래그먼트 렌더링
    return jsonify(html=html, next_cursor=next_cursor)

# 회원정보 수정
@app.route("/edit", methods=['POST', 'GET'])
def update_user():
    token = request.cookies.get('access_token')  # 브라우저 쿠키에서 JWT 토큰을 가져옴
    if not token:
        # return jsonify({'result': 'fail', 'message': '인증이 필요합니다.'}), 401  # 인증 없으면 401 에러
        redirect('/login')

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])  # 토큰 복호화
        user_id = payload['id']  # 토큰에서 사용자 ID 추출
        user = users_collection.find_one({'id': user_id})  # DB에서 사용자 정보 조회
        if not user:
            # return jsonify({'result': 'fail', 'message': '사용자가 존재하지 않습니다.'}), 404  # 사용자가 없는 경우
           return redirect('/login')
    except (ExpiredSignatureError, InvalidTokenError):
        return redirect('/login')

    if request.method == 'GET':
        return render_template('base.html', user=user)

    # except jwt.ExpiredSignatureError:  # 만료된 토큰 처리
    #     return jsonify({'result': 'fail', 'message': '토큰이 만료되었습니다. 로그인해주세요.'}), 401
    # except jwt.InvalidTokenError:  # 잘못된 토큰 처리
    #     return jsonify({'result': 'fail', 'message': '잘못된 토큰입니다. 다시 로그인해주세요.'}), 401

    # 사용자 정보 수정 함수 호출
    data = request.json
    if 'id' not in data:
        return jsonify({'result': 'fail', 'message': '아이디는 필수 입력입니다.'}), 400

    result = update_user_info(data, users_collection)
    return jsonify(result)


@app.route('/blog_edit', methods=['GET'])
def blog_edit():
    token = request.cookies.get('access_token')
    if not token:
        return redirect('/login')

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload['id']
        user = users_collection.find_one({'id': user_id})
        if not user:
            return redirect('/login')
    except (ExpiredSignatureError, InvalidTokenError):
        return redirect('/login')

    cards = list(posts_collection.find())

    return render_template('blog_edit.html', cards=cards, user=user)

@app.route('/profile_edit', methods=['GET'])
def profile_edit():
    token = request.cookies.get('access_token')
    if not token:
        return redirect('/login')

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('id')
        user = users_collection.find_one({'id': user_id})
        if not user:
            return redirect('/login')
    except (ExpiredSignatureError, InvalidTokenError):
        return redirect('/login')

    return render_template('profile_edit.html', user=user)


@app.route('/update_profile', methods=['POST'])
def update_profile():
    # 쿠키에서 토큰을 가져와 복호화
    token = request.cookies.get('access_token')
    if not token:
        return redirect('/login')

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('id')
    except Exception as e:
        return redirect('/login')

    # 요청 데이터 가져오기
    form_data = request.form.to_dict()
    form_data['id'] = user_id  # 토큰에서 추출한 id를 form 데이터에 추가

    # 서비스 함수 호출
    result = update_user_info(form_data, users_collection)

    # 처리 결과에 따라 응답
    if result['result'] == 'success':
        return render_template('profile_edit.html', message="수정 완료!", user=form_data)
    else:
        return render_template('profile_edit.html', message=result['message'], user=form_data)

@app.route('/update_blog', methods=['POST'])
def update_blog():
    update_user_info
    return



if __name__ == '__main__':
    app.run(debug=True)
