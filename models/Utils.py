class Utils():
    
    def get_nickname(from_user):
        if from_user['username']:
            nickname = '@' + from_user['username']
        else:
            nickname = from_user['first_name']
        
        return nickname

