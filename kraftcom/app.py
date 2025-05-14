from flask import Flask, request, jsonify, render_template, make_response, redirect
from services.edit_service import update_user_info
from services.user_service import register_user
from services.auth_service import login_user
from pymongo import MongoClient
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta

app = Flask(__name__)
SECRET_KEY = 'apple'

# MongoDB 연결
client = MongoClient('mongodb://abc1:abc1@54.180.249.140', 27017)
db = client['JungleCom']
users_collection = db['users']
crawlJobs_collection = db['crawl_jobs']
posts_collection = db['posts']

PAGE = 20

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# 회원가입
@app.route('/register', methods=['POST'])
def register():
    data = request.form.to_dict()
    required = ['name', 'id', 'password', 'email', 'season']        # 필수 항목만
    if not all(data.get(f) for f in required):
        return jsonify({'result': 'fail', 'message': '필수 항목을 모두 입력해주세요'}), 400

    result = register_user(data, users_collection, crawlJobs_collection)
    return redirect('./')

# 로그인
@app.route('/login', methods=['POST'])
def login():
    data = request.form.to_dict()
    user_id = data.get('id')
    password = data.get('password')

    if not user_id or not password:
        return "ID와 비밀번호를 입력해주세요.", 400     # ID 또는 PW가 비어 있을 경우 400 반환

    result = login_user(user_id, password, users_collection, SECRET_KEY)    # login_user 모듈에서 사용자 존애 여부, 비밀번호 일치 검증
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
    response = make_response(redirect('/login'))    # /logout에 접근했을 때, 서버가 login 페이지로 이동
    response.set_cookie('access_token', '', max_age=0)  # 쿠키 삭제 : set_cookie는 쿠키를 설정하는 함수지만, value는 빈 문자열, max_age = 0(만료시간 0초라는 의미)을 함께 지정하면 쿠키 삭제 의미
    return response

CARDS = list(posts_collection.find())

def slice_page(cursor: int):
    subset = [c for c in CARDS if c["_id"] < cursor] if cursor else CARDS
    subset = subset[: PAGE + 1]
    next_cur = subset[-1]["_id"] if len(subset) > PAGE else None
    return subset[:PAGE], next_cur

@app.route("/")
def home():
    token = request.cookies.get('access_token')
    user_id = None

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('id')
        except ExpiredSignatureError:
            print("token expired")
        except InvalidTokenError:
            print("invalid token")

    print(user_id)

    cards, next_cursor = slice_page(cursor=0) # 메인 화면에서는 cursor가 0
    return render_template("home.html", cards=cards, next_cursor=next_cursor, user_id=user_id)

@app.route("/api/cards")
def api_cards():
    cursor = int(request.args.get("cursor", 0))
    cards, next_cursor = slice_page(cursor)
    html = render_template("_card_frag.html", cards=cards)
    return jsonify(html=html, next_cursor=next_cursor)


# 회원정보 수정
@app.route("/mypage/edit", methods=['POST'])
def update_user():
    token = request.cookies.get('access_token')  # 브라우저 쿠키에서 JWT 토큰을 가져옴
    if not token:
        return jsonify({'result': 'fail', 'message': '인증이 필요합니다.'}), 401  # 인증 없으면 401 에러

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])  # 토큰 복호화
        user_id = payload['id']  # 토큰에서 사용자 ID 추출
        user = users_collection.find_one({'id': user_id})  # DB에서 사용자 정보 조회

        if not user:
            return jsonify({'result': 'fail', 'message': '사용자가 존재하지 않습니다.'}), 404  # 사용자가 없는 경우

    except jwt.ExpiredSignatureError:  # 만료된 토큰 처리
        return jsonify({'result': 'fail', 'message': '토큰이 만료되었습니다. 로그인해주세요.'}), 401
    except jwt.InvalidTokenError:  # 잘못된 토큰 처리
        return jsonify({'result': 'fail', 'message': '잘못된 토큰입니다. 다시 로그인해주세요.'}), 401

    # 사용자 정보 수정 함수 호출
    data = request.json
    if 'id' not in data:
        return jsonify({'result': 'fail', 'message': '아이디는 필수 입력입니다.'}), 400

    result = edit_service.update_user_info(data, users_collection)
    return jsonify(result)



if __name__ == '__main__':
    app.run(debug=True)
