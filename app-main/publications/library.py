import ipaddress



def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]  # proxies can send list of IPs, with client's IP as the first one
    else:
        ip = request.META.get('REMOTE_ADDR')  # this is the actual IP if no proxies were involved
    return ip


def is_private(ip):
    return ipaddress.ip_address(ip).is_private