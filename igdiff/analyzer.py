from loguru import logger


def extract_usernames(json_data, key=None):
    """Extract usernames from Instagram export JSON."""
    if not json_data:
        return []

    items = json_data[key] if key and key in json_data else json_data

    if isinstance(items, dict):
        items = [items]

    usernames = []

    for item in items:
        if 'title' in item and item['title'] != '':
            usernames.append(item['title'])
        elif 'string_list_data' in item:
            usernames.append(item['string_list_data'][0]['value'])

    return usernames


def find_differences(followers_json, following_json):
    """Compare followers and following to find differences."""
    key_followers = None
    if isinstance(followers_json, dict) and 'relationships_followers' in followers_json:
        key_followers = 'relationships_followers'

    followers = extract_usernames(followers_json, key_followers)
    following = extract_usernames(following_json, 'relationships_following')

    logger.debug(f"Followers count: {len(followers)}")
    logger.debug(f"Following count: {len(following)}")

    not_following_you = [p for p in following if p not in followers]
    you_not_following = [p for p in followers if p not in following]

    return not_following_you, you_not_following
