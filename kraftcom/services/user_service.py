from werkzeug.security import generate_password_hash        # 비밀번호를 SHA256 기반으로 안전하게 암호
from datetime import datetime

def register_user(data, users_collection, crawlJobs_collection):      # json 형식의 data (브라우저를 통해 받은 회원가입 정보)
    user_id = data['id']

    # ID 중복 확인
    if users_collection.find_one({'id': user_id}):
        return {'result': 'fail', 'message': '이미 존재하는 아이디입니다.'}

    # 비밀번호 해시 처리  --> HASH + salt 조합을 사용하여 비밀번호 암호화
    hashed_pw = generate_password_hash(data['password'])

    # MongoDB에 저장할 데이터 
    user_doc = {
        'name': data['name'],
        'id': user_id,
        'password': hashed_pw,
        'email': data['email'],
        'season': data['season'],
        'blog': data.get('blog', ''),  # 공백 가능
        'created_at': datetime.utcnow()
    }

    user_result = users_collection.insert_one(user_doc)
    user_id_object = user_result.inserted_id  # MongoDB의 ObjectId

    job_doc = {
        'blog_id': user_id_object,             # 사용자와 연결
        'check_date': datetime.utcnow(),       # 현재 시각 (ISODate로 저장됨)
        'locked': False                        # 초기 상태는 크롤링 안 함
    }

    crawlJobs_collection.insert_one(job_doc)            #crawls_job 컬렉션에 저장
    return {'result': 'success', 'message': '회원가입이 완료되었습니다.'}
