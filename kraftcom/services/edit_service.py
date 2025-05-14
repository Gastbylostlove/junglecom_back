from werkzeug.security import generate_password_hash
from datetime import datetime

def update_user_info(data, users_collection):
    user_id = data['id']
    
    # 사용자 정보 확인
    user = users_collection.find_one({'id': user_id})
    if not user:
        return {'result': 'fail', 'message': '사용자를 찾을 수 없습니다.'}
    
    # 수정할 데이터 초기화
    update_data = {}

    # 비밀번호 수정
    if 'password' in data and data['password']:
        # 비밀번호가 변경될 경우 해시 처리
        hashed_pw = generate_password_hash(data['password'], method='pbkdf2:sha256')
        update_data['password'] = hashed_pw

    # 블로그 수정
    if 'blog' in data:
        update_data['blog'] = data['blog']
    
    # 업데이트가 필요한 데이터가 있다면
    if update_data:
        # 사용자의 정보 업데이트
        users_collection.update_one({'id': user_id}, {'$set': update_data})
        return {'result': 'success', 'message': '회원 정보가 수정되었습니다.'}
    
    return {'result': 'fail', 'message': '변경된 정보가 없습니다.'}
