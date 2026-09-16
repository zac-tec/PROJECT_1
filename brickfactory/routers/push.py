"""Authenticated, device-specific push subscription management."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from database import get_connection
from dependencies import get_current_user
from push_notifications import public_config, validate_subscription

router = APIRouter(prefix='/notifications', tags=['notifications'])

class Endpoint(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2048)

class Keys(BaseModel):
    p256dh: str = Field(max_length=128)
    auth: str = Field(max_length=64)

class Subscription(Endpoint):
    keys: Keys

@router.get('/config')
def config(response: Response, user=Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return public_config()

@router.post('/subscribe')
def subscribe(body: Subscription, user=Depends(get_current_user)):
    if not public_config()['enabled']:
        raise HTTPException(503, 'Notifications are not configured yet.')
    try:
        validate_subscription(body.endpoint, body.keys.p256dh, body.keys.auth)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid or unsupported push subscription.')
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute('''INSERT INTO push_subscriptions(endpoint,username,session_version,p256dh,auth)
                         VALUES(%s,%s,%s,%s,%s) ON CONFLICT(endpoint) DO UPDATE SET
                         username=excluded.username,session_version=excluded.session_version,
                         p256dh=excluded.p256dh,auth=excluded.auth,updated_at=now()''',
                      (body.endpoint,user['username'],user.get('session_version',0),body.keys.p256dh,body.keys.auth))
        conn.commit()
        return {'enabled': True}
    finally:
        conn.close()

@router.post('/unsubscribe')
def unsubscribe(body: Endpoint, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute('DELETE FROM push_subscriptions WHERE endpoint=%s AND username=%s', (body.endpoint,user['username']))
        conn.commit()
        return {'enabled': False}
    finally:
        conn.close()
