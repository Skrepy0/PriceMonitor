import requests

from controller import HEADERS, BASE_URL

DEFAULT_RULES = {
    'gpt': 'OpenAI',
    'dall-e': 'OpenAI',
    'whisper': 'OpenAI',
    'o1': 'OpenAI',
    'o3': 'OpenAI',
    'claude': 'Anthropic',
    'gemini': 'Google',
    'moonshot': 'Moonshot',
    'kimi': 'Moonshot',
    'chatglm': '智谱',
    'glm-': '智谱',
    'qwen': '阿里巴巴',
    'deepseek': 'DeepSeek',
    'abab': 'MiniMax',
    'minimax': 'MiniMax',
    'ernie': '百度',
    'spark': '讯飞',
    'hunyuan': '腾讯',
    'command': 'Cohere',
    '@cf/': 'Cloudflare',
    '360': '360',
    'yi': '零一万物',
    'jina': 'Jina',
    'mistral': 'Mistral',
    'grok': 'xAI',
    'llama': 'Meta',
    'doubao': '字节跳动',
    'kling': '快手',
    'jimeng': '即梦',
    'vidu': 'Vidu',
}


def get_vendor_id_by_model(model: dict) -> int:
    keyword = ''
    model_name = model['model_name']
    for key, value in DEFAULT_RULES.items():
        if value.lower() in model_name.lower():
            keyword = value
    if keyword or keyword == '':
        keyword = model.get('icon')
        if keyword and keyword != '':
            keyword = keyword.lower()
    if keyword and keyword != '':
        resp = requests.get(
            f'{BASE_URL}/api/vendors/search',
            params={'keyword': keyword, 'p': 1, 'page_size': 20},
            headers=HEADERS,
        )
        data = resp.json()
        if data['success']:
            items = data.get('data').get('items')
            if len(items) != 0:
                res = items[0].get(id)
                return res if res else -1
    return -1


def translate_vendor(
    upstream_vendors: list[dict], station_vendors: list[dict], vendor_id: int
):
    up_vendors = {}
    st_vendors = {}
    for item in upstream_vendors:
        up_vendors[item['id']] = item['name'].lower()
    for item in station_vendors:
        st_vendors[item['name'].lower()] = item['id']
    res = st_vendors.get(up_vendors.get(vendor_id))
    return res if res else -1
