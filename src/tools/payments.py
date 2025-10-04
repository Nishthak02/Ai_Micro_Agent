from urllib.parse import urlencode


def generate_upi_link(pa: str, pn: str, am: str, tn: str = None):
    params = {'pa': pa, 'pn': pn, 'am': str(am), 'cu': 'INR'}
    if tn:
        params['tn'] = tn
    return {'upi_link': 'upi://pay?' + urlencode(params)}