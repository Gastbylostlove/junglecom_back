from flask import Flask, request, jsonify, render_template, make_response, redirect, session
from services.edit_service import update_user_info      # 사용자 정보 수정 서비스 함수
from services.user_service import register_user         # 회원가입 처리 함수
from services.auth_service import login_user            # 로그인 처리 함수
from services.auth_service import get_user_by_id        # 사용자 ID로 정보 조회
from pymongo import MongoClient                         # MongoDB와 연결하기 위한 클라이언트
import jwt                  # JWT 사용
from jwt import ExpiredSignatureError, InvalidTokenError        # JWT 예외 처리용
from datetime import datetime, timedelta        # 토큰 유효 시간 설정에  사용
import os       # OS 환경 변수 접근
from dotenv import load_dotenv      # .env 파일에서 환경 변수 로드
from bson import ObjectId
from services.user_service import animal_icons

# .env 로드 및 환경 변수 설정
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')          # MongoDB URI 주소
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')      # 사용할 MongoDB 데이터베이스 이름

app = Flask(__name__)
SECRET_KEY = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
app.secret_key = SECRET_KEY

# MongoDB 클라이언트 연결 및 DB 생성
client = MongoClient('mongodb://abc1:abc1@54.180.249.140:27017')
db = client[MONGO_DB_NAME]

# DB 컬레션 참조 변수
users_collection = db['users']      # 사용자 정보 저장 컬렉션
crawlJobs_collection = db['crawl_jobs']     # 크롤링 잡 정보
posts_collection = db['posts']          # 게시글 정보 저장 컬렉션

# PAGE = 50       # 페이징 처리를 위한 한 페이지 당 카드 수

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

# 로그아웃
@app.route('/logout')
def logout():
    response = make_response(redirect('/'))    # /logout에 접근했을 때, 서버가 login 페이지로 이동
    response.set_cookie('access_token', '', max_age=0)  # 쿠키 삭제 : set_cookie는 쿠키를 설정하는 함수지만, value는 빈 문자열, max_age = 0(만료시간 0초라는 의미)을 함께 지정하면 쿠키 삭제 의미
    return response

@app.route('/', methods=['GET'])
def home():
    token = request.cookies.get('access_token')
    user_id = None
    profile_image = 'default.png'  # 기본값
    keyword = request.args.get('search')

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
    
    if keyword is not None:
        posts = posts_collection.find({
            "$or": [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}}
            ]
            })
        posts = list(posts.sort("_id", -1))
    else:
        posts = list(posts_collection.find({"viewToggle": True}).sort("_id", -1))

    for post in posts:
        user = db.users.find_one({'_id': ObjectId(post['userId'])})
        if user:
            season = user.get('season', '미정')
            name = user.get('name', '알 수 없음')
            post['icon'] = animal_icons[season]
            post['user_display'] = f"{season}기-{name}"
        else:
            post['icon'] = None
            post['user_display'] = "미정-알 수 없음"

    return render_template(
        "home.html",
        cards=posts,
        user_id=user_id,
        profile_image=profile_image
    )

@app.route('/viewtoggle_edit', methods=['POST'])
def viewtoggle_edit():
    qwe = request.form["card_viewToggle"]
    ewq = qwe
    if request.form["card_viewToggle"] == 'True':
        insert = False
    else:
        insert = True

    posts_collection.update_one(
        {
            "guid": request.form["card_guid"]
        },
        {
            "$set" :
                {
                    "viewToggle" : insert
                }
        }
    )
    return redirect('/blog_edit')

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

    cards = posts_collection.find({"userId": user['_id']}).sort("_id", -1)

    return render_template('blog_edit.html', cards=list(cards), user=user)

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
