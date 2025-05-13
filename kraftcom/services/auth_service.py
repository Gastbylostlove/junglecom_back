import jwt
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta

# 로그인
def login_user(user_id, password, users_collection, secret_key):    # 로그인 폼에서 입력한 ID, pw, users 컬렉션, 토큰 서명에 사용하게될 비밀키
    user = users_collection.find_one({'id': user_id})
    
    # ID 확인
    if not user:
        return {'result': 'fail', 'message': '존재하지 않는 사용자입니다.'}

    # PW 확인
    if not check_password_hash(user['password'], password):     # user['password']는 회원 가입시 저장된 해시된 PW, password는 사용자가 입력한 비밀번호 두 개를 일치하는지 확인하는 함수
        return {'result': 'fail', 'message': '비밀번호가 일치하지 않습니다.'}

    #JWT 토큰 페이로드 구성
    payload = {
        'id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=3)       # 토큰 만료시간
    }

    token = jwt.encode(payload, secret_key, algorithm='HS256')      # 토큰 생성

    return {
        'result': 'success',
        'message': '로그인 성공',
        'token': token
    }
