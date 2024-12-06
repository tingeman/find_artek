import secrets


def generate_secret_key():
    return secrets.token_hex(32)

def run():
    print(generate_secret_key())

if __name__ == "__main__":
    run()