# def is_not_utf8(char):
#     try:
#         char.encode('utf-8').decode('utf-8')
#         return False
#     except UnicodeDecodeError:
#         return True
    
# print(is_not_utf8('‐'))
# print(is_not_utf8('-'))

# # check if these to values are equal
# # print(ascii_or_uf8_code == 8211)


# def check_ascii_codes(string, valid_codes):
#     code_map = {'-': 45, '+': 43, '=': 61} # add any other mappings as needed
#     for char in string:
#         code = code_map.get(char, ord(char))
#         if code not in valid_codes:
#             return False
#     return True

# string = "10 - 5 = 5"
# valid_codes = [32, 43, 45, 48, 49, 50, 53, 61] # valid codes for space, plus, minus, digits 0-9, and equals sign
# if check_ascii_codes(string, valid_codes):
#     print(f"All characters in '{string}' have valid ASCII codes")
# else:
#     print(f"Some characters in '{string}' have invalid ASCII codes")


# # valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# def check_ascii_codes(string, valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61}):
#     code_map = {'-': 45, '+': 43, '=': 61} # add any other mappings as needed
#     for char in string:
#         code = code_map.get(char, ord(char))
#         if code not in valid_codes.values():
#             return False
#     return True

# valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# string = "10 ‐ 5 = 5"
# if check_ascii_codes(string, valid_codes):
#     print(f"All characters in '{string}' have valid ASCII codes")
# else:
#     print(f"Some characters in '{string}' have invalid ASCII codes")



# def check_ascii_codes(string, valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61}):
#     code_map = {'-': 45, '+': 43, '=': 61} # add any other mappings as needed
#     for char in string:
#         code = code_map.get(char, ord(char))
#         if code not in valid_codes.values():
#             return False
#     return True

# valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# string = "10 ‐ 5 = 5"
# if check_ascii_codes(string, valid_codes):
#     print(f"All characters in '{string}' have valid ASCII codes")
# else:
#     print(f"Some characters in '{string}' have invalid ASCII codes")    












# class InvalidASCIICodeException(Exception):
#     def __init__(self, message):
#         super().__init__(message)

# def check_ascii_codes(string, valid_codes):
#     code_map = {'-': 45, '+': 43, '=': 61} # add any other mappings as needed
#     for i, char in enumerate(string):
#         code = code_map.get(char, ord(char))
#         if code not in valid_codes.values():
#             invalid_char = string[i]
#             raise InvalidASCIICodeException(f"Invalid ASCII code found: '{invalid_char}' (code {code}) at position {i}")
#     return True

# valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# string = "10 ‐ 5 = 5"

# try:
#     check_ascii_codes(string, valid_codes)
#     print(f"All characters in '{string}' have valid ASCII codes")
# except InvalidASCIICodeException as e:
#     print(e)







# valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# string = "10 ‐ 5 = 5"

# try:
#     check_ascii_codes(string, valid_codes)
#     print(f"All characters in '{string}' have valid ASCII codes")
# except InvalidASCIICodeException as e:
#     print(e)




# class InvalidASCIICodeException(Exception):
#     def __init__(self, message, position, invalid_char, replacement_char=None):
#         super().__init__(message)
#         self.position = position
#         self.invalid_char = invalid_char
#         self.replacement_char = replacement_char

#     def __str__(self):
#         error_message = f"Invalid ASCII code found: '{self.invalid_char}' (code {ord(self.invalid_char)}) at position {self.position}"
#         if self.replacement_char is not None:
#             error_message += f", replaced with '{self.replacement_char}'"
#         return error_message

# def check_ascii_codes(string, valid_codes, replacement_char=None):
#     code_map =          {'-': 45, 'é': 233} # add any other mappings as needed
#     invalid_code_map =  {'‐': 8208, 'é': 233} # here you add the evil twin, so can autocorrect instead of raising an
#     new_string = ''
#     for i, char in enumerate(string):
#         code = code_map.get(char, ord(char))
#         if code not in valid_codes.values():
#             invalid_char = string[i]
#             if replacement_char is not None:
#                 new_string += replacement_char
#             else:
#                 new_string += invalid_char
#             raise InvalidASCIICodeException(f"Invalid ASCII code found: '{invalid_char}' (code {code}) at position {i}", i, invalid_char, replacement_char)
#         else:
#             new_string += char
#     return new_string

# valid_codes = {' ': 32, '+': 43, '-': 45, '0': 48, '1': 49, '2': 50, '5': 53, '=': 61} # valid codes for space, plus, minus, digits 0-9, and equals sign
# string = "10 ø é ‐ é5 = 5"

# try:
#     new_string = check_ascii_codes(string, valid_codes, '*')
#     print(f"All characters in '{new_string}' have valid ASCII codes")
# except InvalidASCIICodeException as e:
#     print(e)


# def check_string(input_string):
#     invalid_chars = set(['a', 'ø', 'å'])
#     for i, char in enumerate(input_string):
#         if char in invalid_chars:
#             error_message = f"Invalid character found: '{char}' at position {i}"
#             raise ValueError(error_message)
#     return True

# input_string = "some string with invalid characters ø and å"

# try:
#     check_string(input_string)
# except ValueError as e:
#     invalid_char = e.args[0].split("'")[1]
#     input_string = input_string.replace(invalid_char, '')


# print(input_string)



# def check_string(input_string):
#     invalid_to_valid = {
#         '‐': '.'
#     }
#     invalid_indices = []
#     for i, char in enumerate(input_string):
#         if char in invalid_to_valid:
#             invalid_indices.append(i)
#     return invalid_indices

# input_string = "some ‐ string ‐ with ‐ invalid characters ø and å"

# invalid_to_valid = {
#     '‐': '.',
# }

# while True:
#     input_bytes = input_string.encode('utf-8')
#     invalid_indices = check_string(input_bytes.decode('utf-8'))
#     if not invalid_indices:
#         break
#     for i in invalid_indices:
#         invalid_char = input_string[i]
#         if invalid_char in invalid_to_valid:
#             replacement = invalid_to_valid[invalid_char]
#             input_string = input_string[:i] + replacement + input_string[i+1:]
# print(input_string)









invalid_to_valid = {
    '‐': '-'
}

def check_string(input_string):
    invalid_indices = []
    for i, char in enumerate(input_string):
        if char in invalid_to_valid:
            invalid_indices.append(i)
    return invalid_indices

input_string = "some ‐ string ‐ with ‐ invalid characters ø and å"

while True:
    input_bytes = input_string.encode('utf-8')
    invalid_indices = check_string(input_bytes.decode('utf-8'))
    if not invalid_indices:
        break
    for i in invalid_indices:
        invalid_char = input_string[i]
        if invalid_char in invalid_to_valid:
            replacement = invalid_to_valid[invalid_char]
            input_string = input_string[:i] + replacement + input_string[i+1:]


print(input_string)