import redis 

def redis_test():
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set('test_key', 'test_value')
    value = r.get('test_key')
    return value.decode('utf-8') if value else None 

if __name__ == "__main__":
    result = redis_test()
    print(f"Redis test result: {result}")