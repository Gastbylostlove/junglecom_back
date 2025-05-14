from werkzeug.security import generate_password_hash        # 비밀번호를 SHA256 기반으로 안전하게 암호
from datetime import datetime

animal_icons = {
    1: "monkey.png",
    2: "cow.png",
    3: "panda.png",
    4: "polar.png",
    5: "bear.png",
    6: "mouse.png",
    7: "frog.png",
    8: "hamster.png",
    9: "koala.png"
}


def register_user(data, users_collection, crawlJobs_collection):      # json 형식의 data (브라우저를 통해 받은 회원가입 정보)
    user_id = data['id']

    # ID 중복 확인
    if users_collection.find_one({'id': user_id}):
        return {'result': 'fail', 'message': '이미 존재하는 아이디입니다.'}

    # 비밀번호 해시 처리  --> HASH + salt 조합을 사용하여 비밀번호 암호화
    hashed_pw = generate_password_hash(data['password'])
    
    # season 값에 대한 검증 (필수 값 체크)
    season = data.get('season')
    if not season:
        return {'result': 'fail', 'message': 'Season 값은 필수 입력입니다.'}

    # season 값에 따라 동물 아이콘 선택
    season = int(season)
    
    # season 값에 맞는 아이콘이 존재하는지 확인
    if season not in animal_icons:
        return {'result': 'fail', 'message': '유효하지 않은 시즌 값입니다. (1~9 사이의 값만 가능)'}
    
    animal_icon = animal_icons[season]  # 해당 season에 맞는 아이콘 URL
    

    # MongoDB에 저장할 데이터 
    user_doc = {
        'name': data['name'],
        'id': user_id,
        'password': hashed_pw,
        'email': data['email'],
        'season': season,
        'blog': data.get('blog', ''),  # 공백 가능
        'profile_image' : animal_icon,
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
