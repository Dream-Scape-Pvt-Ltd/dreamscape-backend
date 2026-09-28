from urllib.parse import urlsplit
from rest_framework import serializers


def text(value, limit=12000):
    if not isinstance(value, str) or len(value) > limit:
        raise serializers.ValidationError('Content must be text within the length limit.')
    return value


def strings(value):
    if not isinstance(value, list) or len(value) > 80:
        raise serializers.ValidationError('Use a list of up to 80 paragraphs.')
    return [text(v) for v in value]


def records(value, keys, limit=30):
    if not isinstance(value, list) or len(value) > limit:
        raise serializers.ValidationError('Too many content entries.')
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != set(keys):
            raise serializers.ValidationError('Each entry must include the expected fields.')
        result.append({key: validator(item[key]) for key, validator in keys.items()})
    return result


def validate_company(value):
    paragraphs = ['intro','home','beyond','ceo','story','why','team','amar','saput','santa','responsibility']
    if not isinstance(value, dict) or set(value) - set(paragraphs + ['team_profiles','principles','responsibilities','image','ceo_name','ceo_role']):
        raise serializers.ValidationError('Unrecognized company content.')
    clean = {key: strings(item) for key, item in value.items() if key in paragraphs}
    if 'intro' in clean and not clean['intro']:
        raise serializers.ValidationError('Add at least one introduction paragraph.')
    if 'team_profiles' in value:
        profiles = value['team_profiles']
        if not isinstance(profiles, list) or len(profiles) > 30:
            raise serializers.ValidationError('Too many team profiles.')
        clean['team_profiles'] = []
        for profile in profiles:
            if not isinstance(profile, dict) or set(profile) - {'name','role','paragraphs','image'} or not {'name','role','paragraphs'} <= set(profile):
                raise serializers.ValidationError('Each team profile needs a name, role and biography.')
            clean['team_profiles'].append({
                'name': text(profile['name'], 180),
                'role': text(profile['role'], 180),
                'paragraphs': strings(profile['paragraphs']),
                'image': image(profile['image']) if profile.get('image') else '',
            })
    for key in ['principles','responsibilities']:
        if key in value:
            clean[key] = records(value[key], {'title':text,'paragraphs':strings})
    for key in ['image','ceo_name','ceo_role']:
        if key in value:
            clean[key] = image(value[key]) if key=='image' else text(value[key],180)
    return clean


def validate_partner(value):
    if not isinstance(value, dict) or set(value) - {'title','accent','description','partners','offers','steps','image','who_title','offer_title','steps_title','enquiry_title','enquiry_description'}:
        raise serializers.ValidationError('Unrecognized partner content.')
    return {key: records(item, {'title':text,'text':text}) if key in ['partners','offers','steps'] else image(item) if key=='image' else text(item)
            for key, item in value.items()}


def image(value):
    value = text(value, 500)
    url = urlsplit(value)
    if not (value.startswith('/images/') and not value.startswith('//')) and not (url.scheme in ['http','https'] and url.netloc and not url.username and not url.password):
        raise serializers.ValidationError('Use an http(s) image URL or an /images/ path.')
    return value


def validate_gallery(value):
    return records(value, {'image':image,'title':text,'group':text}, limit=100)
