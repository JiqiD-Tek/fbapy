"""小雅开放平台接口注册表。"""

from __future__ import annotations

from .models import XimalayaEndpoint

# key 统一使用 "分组.方法名" 形式，便于客户端按分组分发调用。
ENDPOINTS: dict[str, XimalayaEndpoint] = {
    'oauth.get_login_url': XimalayaEndpoint(
        'oauth',
        'get_login_url',
        '/get_login_url',
        'GET',
        '4.1.1',
        'Get OAuth login URL.',
    ),
    'oauth.get_token_info': XimalayaEndpoint(
        'oauth', 'get_token_info', '/oauth2/get_token_info', 'GET', '4.1.2', 'Get access token details.'
    ),
    'oauth.refresh_token': XimalayaEndpoint(
        'oauth', 'refresh_token', '/oauth2/refresh_token', 'GET', '4.1.3', 'Refresh an OAuth access token.'
    ),
    'oauth.secure_access_token': XimalayaEndpoint(
        'oauth',
        'secure_access_token',
        '/oauth2/secure_access_token',
        'GET',
        '4.1.4',
        'Get a temporary device access token.',
    ),
    'on_demand.list_categories': XimalayaEndpoint(
        'on_demand', 'list_categories', '/categories/list', 'GET', '4.2.1', 'List on-demand content categories.'
    ),
    'on_demand.list_tags': XimalayaEndpoint(
        'on_demand', 'list_tags', '/v2/tags/list', 'GET', '4.2.2', 'List tags under a category.'
    ),
    'on_demand.list_albums': XimalayaEndpoint(
        'on_demand', 'list_albums', '/v2/albums/list', 'GET', '4.2.3', 'List albums by category and tag.'
    ),
    'on_demand.browse_album': XimalayaEndpoint(
        'on_demand', 'browse_album', '/albums/browse', 'GET', '4.2.4', 'Browse tracks inside an album.'
    ),
    'on_demand.get_albums_batch': XimalayaEndpoint(
        'on_demand', 'get_albums_batch', '/albums/get_batch', 'GET', '4.2.5', 'Batch get album details.'
    ),
    'on_demand.get_album_updates_batch': XimalayaEndpoint(
        'on_demand',
        'get_album_updates_batch',
        '/albums/get_update_batch',
        'GET',
        '4.2.6',
        'Batch get album update info.',
    ),
    'on_demand.get_tracks_batch': XimalayaEndpoint(
        'on_demand', 'get_tracks_batch', '/tracks/get_batch', 'GET', '4.2.7', 'Batch get track details.'
    ),
    'on_demand.get_last_play_tracks': XimalayaEndpoint(
        'on_demand',
        'get_last_play_tracks',
        '/tracks/get_last_play_tracks',
        'GET',
        '4.2.8',
        'Get related page info for a track inside an album.',
    ),
    'on_demand.list_metadata': XimalayaEndpoint(
        'on_demand', 'list_metadata', '/v2/metadata/list', 'GET', '4.2.9', 'List metadata for a category.'
    ),
    'on_demand.list_metadata_albums': XimalayaEndpoint(
        'on_demand',
        'list_metadata_albums',
        '/v2/metadata/albums',
        'GET',
        '4.2.10',
        'List albums filtered by metadata.',
    ),
    'on_demand.search_columns': XimalayaEndpoint(
        'on_demand',
        'search_columns',
        '/operation/search_columns',
        'GET',
        '4.2.11',
        'Search columns with multiple filters.',
    ),
    'on_demand.get_columns_batch': XimalayaEndpoint(
        'on_demand', 'get_columns_batch', '/v2/columns/get_batch', 'GET', '4.2.12', 'Batch get column details.'
    ),
    'on_demand.browse_column': XimalayaEndpoint(
        'on_demand', 'browse_column', '/v2/columns/browse', 'GET', '4.2.13', 'Browse column content.'
    ),
    'on_demand.batch_get_track_play_info': XimalayaEndpoint(
        'on_demand',
        'batch_get_track_play_info',
        '/openapi_play_url/tracks/batch_get_play_info',
        'GET',
        '4.2.14',
        'Batch get free track play URLs.',
    ),
    'search.search_albums': XimalayaEndpoint(
        'search',
        'search_albums',
        '/v2/search/albums',
        'GET',
        '4.3.1',
        'Search albums.',
    ),
    'search.search_tracks': XimalayaEndpoint(
        'search',
        'search_tracks',
        '/v2/search/tracks',
        'GET',
        '4.3.2',
        'Search tracks.',
    ),
    'search.hot_words': XimalayaEndpoint(
        'search',
        'hot_words',
        '/search/hot_words',
        'GET',
        '4.3.3',
        'Get hot search words.',
    ),
    'search.suggest_words': XimalayaEndpoint(
        'search', 'suggest_words', '/search/suggest_words', 'GET', '4.3.4', 'Get search suggestions.'
    ),
    'search.text_search': XimalayaEndpoint(
        'search', 'text_search', '/os/v2/text/search/v2', 'GET', '4.3.5', 'Perform NLP-aware text search.'
    ),
    'recommendation.guess_like_albums': XimalayaEndpoint(
        'recommendation', 'guess_like_albums', '/v2/albums/guess_like', 'GET', '4.4.1', 'Get guess-you-like albums.'
    ),
    'recommendation.relative_albums_by_album': XimalayaEndpoint(
        'recommendation',
        'relative_albums_by_album',
        '/v2/albums/relative_album',
        'GET',
        '4.4.2',
        'Get related albums by album id.',
    ),
    'recommendation.relative_albums_by_track': XimalayaEndpoint(
        'recommendation',
        'relative_albums_by_track',
        '/v2/tracks/relative_album',
        'GET',
        '4.4.3',
        'Get related albums by track id.',
    ),
    'recommendation.one_click_channels': XimalayaEndpoint(
        'recommendation',
        'one_click_channels',
        '/one_click_listen/channels',
        'GET',
        '4.4.4',
        'Get one-click-listen channels.',
    ),
    'recommendation.one_click_next_track': XimalayaEndpoint(
        'recommendation',
        'one_click_next_track',
        '/one_click_listen/get_next_track',
        'GET',
        '4.4.5',
        'Get next track for a one-click-listen channel.',
    ),
    'recommendation.list_scenes': XimalayaEndpoint(
        'recommendation',
        'list_scenes',
        '/scenes/one_click_listen/scenes',
        'GET',
        '4.4.6',
        'List recommendation scenes.',
    ),
    'recommendation.list_scene_channels': XimalayaEndpoint(
        'recommendation',
        'list_scene_channels',
        '/scenes/one_click_listen/channels',
        'GET',
        '4.4.7',
        'List channels under a scene.',
    ),
    'recommendation.list_scene_tracks': XimalayaEndpoint(
        'recommendation',
        'list_scene_tracks',
        '/scenes/one_click_listen/tracks',
        'GET',
        '4.4.8',
        'List tracks under a scene channel.',
    ),
    'user.get_user_info': XimalayaEndpoint(
        'user',
        'get_user_info',
        '/profile/user_info',
        'GET',
        '4.5.1',
        'Get current user profile.',
    ),
    'user.get_persona': XimalayaEndpoint(
        'user',
        'get_persona',
        '/profile/persona',
        'GET',
        '4.5.2',
        'Get current user persona.',
    ),
    'user.get_subscribe_albums_by_uid': XimalayaEndpoint(
        'user',
        'get_subscribe_albums_by_uid',
        '/v2/subscribe/get_albums_by_uid',
        'GET',
        '4.5.3',
        'Get subscribed album updates for current user.',
    ),
    'user.subscribe_add_or_delete': XimalayaEndpoint(
        'user',
        'subscribe_add_or_delete',
        '/subscribe/add_or_delete',
        'POST',
        '4.5.4',
        'Subscribe or unsubscribe an album.',
    ),
    'user.subscribe_batch_add': XimalayaEndpoint(
        'user', 'subscribe_batch_add', '/subscribe/batch_add', 'POST', '4.5.5', 'Subscribe multiple albums.'
    ),
    'user.is_subscribed': XimalayaEndpoint(
        'user', 'is_subscribed', '/v2/subscribe/is_subscribed', 'POST', '4.5.6', 'Check whether albums are subscribed.'
    ),
    'user.get_play_history': XimalayaEndpoint(
        'user', 'get_play_history', '/play_history/get_by_uid', 'GET', '4.5.7', 'Get play history for current user.'
    ),
    'user.batch_upload_play_history': XimalayaEndpoint(
        'user', 'batch_upload_play_history', '/play_history/batch_upload', 'POST', '4.5.8', 'Batch upload play history.'
    ),
    'user.batch_delete_play_history': XimalayaEndpoint(
        'user', 'batch_delete_play_history', '/play_history/batch_delete', 'POST', '4.5.9', 'Batch delete play history.'
    ),
    'collector.batch_track_records': XimalayaEndpoint(
        'collector',
        'batch_track_records',
        '/openapi-collector-app/track_batch_records',
        'POST',
        '4.6.1',
        'Batch upload play data.',
    ),
    'collector.batch_album_browse_records': XimalayaEndpoint(
        'collector',
        'batch_album_browse_records',
        '/openapi-collector-app/album_browse_records',
        'POST',
        '4.6.2',
        'Batch upload album browse records.',
    ),
    'sleep.list_topics': XimalayaEndpoint(
        'sleep',
        'list_topics',
        '/assisted_sleep/topics',
        'GET',
        '4.7.1',
        'List assisted sleep topics.',
    ),
    'sleep.list_cards': XimalayaEndpoint(
        'sleep', 'list_cards', '/assisted_sleep/cards', 'GET', '4.7.2', 'List cards under an assisted sleep topic.'
    ),
    'operation.recommend_albums': XimalayaEndpoint(
        'operation', 'recommend_albums', '/operation/recommend_albums', 'GET', '4.8.1', 'Get daily recommended albums.'
    ),
    'operation.list_categories': XimalayaEndpoint(
        'operation', 'list_categories', '/operation/categories', 'GET', '4.8.2', 'List operation categories.'
    ),
    'operation.list_dimensions': XimalayaEndpoint(
        'operation', 'list_dimensions', '/operation/dimensions', 'GET', '4.8.3', 'List operation dimensions.'
    ),
    'operation.list_tags_of_dimension': XimalayaEndpoint(
        'operation',
        'list_tags_of_dimension',
        '/operation/tags_of_dimension',
        'GET',
        '4.8.4',
        'List tags under a dimension.',
    ),
    'operation.list_dimension_tags': XimalayaEndpoint(
        'operation',
        'list_dimension_tags',
        '/operation/dimension_tags',
        'GET',
        '4.8.5',
        'List all operation dimension tags.',
    ),
    'operation.list_xm_columns': XimalayaEndpoint(
        'operation', 'list_xm_columns', '/operation/xm_columns', 'GET', '4.8.6', 'List Ximalaya system columns.'
    ),
    'operation.batch_get_columns': XimalayaEndpoint(
        'operation', 'batch_get_columns', '/operation/batch_get_columns', 'GET', '4.8.7', 'Batch get operation columns.'
    ),
    'operation.browse_column_content': XimalayaEndpoint(
        'operation',
        'browse_column_content',
        '/operation/browse_column_content',
        'GET',
        '4.8.8',
        'Browse operation column content.',
    ),
    'operation.rank_by_type': XimalayaEndpoint(
        'operation',
        'rank_by_type',
        '/openapi-gateway-app/operation/rank_by_type',
        'GET',
        '4.8.9',
        'Get rank lists by type.',
    ),
    'operation.browse_rank_albums': XimalayaEndpoint(
        'operation',
        'browse_rank_albums',
        '/v2/operation/browse_rank_albums',
        'GET',
        '4.8.10',
        'Browse rank album content.',
    ),
    'reporting.device_activate': XimalayaEndpoint(
        'reporting',
        'device_activate',
        '/openapi-collector-app/reporting/device_activate',
        'POST',
        '4.9.1',
        'Report device activation or activity.',
    ),
    'incremental.list_album_increments': XimalayaEndpoint(
        'incremental', 'list_album_increments', '/incr/albums', 'GET', '4.10.1', 'List incremental album changes.'
    ),
    'incremental.list_track_increments': XimalayaEndpoint(
        'incremental', 'list_track_increments', '/incr/tracks', 'GET', '4.10.2', 'List incremental track changes.'
    ),
    'video.get_video_play_info': XimalayaEndpoint(
        'video', 'get_video_play_info', '/open_pay/get_video_play_info', 'GET', '4.11.1', 'Get a video play URL.'
    ),
    'video.batch_get_video_play_info': XimalayaEndpoint(
        'video',
        'batch_get_video_play_info',
        '/open_pay/batch_get_video_play_info',
        'GET',
        '4.11.2',
        'Batch get video play URLs.',
    ),
}


__all__ = ['ENDPOINTS']
