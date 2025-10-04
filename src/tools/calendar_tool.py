def create_event(title: str, start_iso: str = None, rrule: str = None):
# Return fake event id for now
    return {'event_id': 'evt_' + title[:10].replace(' ', '_')}