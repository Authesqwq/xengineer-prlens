"""EVALUATION FIXTURE ONLY — do not use in production."""

def get_user_name(user_data):
    return user_data["name"]

def get_config_value(config, key):
    return config[key]

def average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)

def get_first_item(items):
    return items[0]

def safe_parse(value):
    try:
        return int(value)
    except ValueError:
        pass
