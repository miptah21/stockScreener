"""
Screener API Routes — Endpoints for technical and simple screening.
"""

import logging
from flask import Blueprint, jsonify, request

from services.screening_service import run_technical_screen, run_simple_screen
from utils.constants import MARKET_CAP_PRESETS

logger = logging.getLogger(__name__)

api_screeners_bp = Blueprint('api_screeners', __name__)


@api_screeners_bp.route('/api/technical-screen', methods=['POST'])
def api_technical_screen():
    """
    Run technical analysis screening on a stock list.

    POST JSON body:
        list (str): Stock list key or 'custom'
        tickers (list): Custom tickers (if list='custom')
        min_market_cap (float): Min market cap filter (optional)
        max_market_cap (float): Max market cap filter (optional)
        market_cap_preset (str): Preset key like 'small', 'mid', 'large' (optional)
    """
    data = request.get_json() or {}
    list_key = data.get('list', '').strip()
    custom_tickers = data.get('tickers', [])
    preset = data.get('market_cap_preset', 'all')
    offset = data.get('offset')
    limit = data.get('limit')

    if not list_key:
        return jsonify({'success': False, 'error': 'Parameter "list" is required.'}), 400

    # Resolve market cap from preset or explicit values
    min_mc = data.get('min_market_cap')
    max_mc = data.get('max_market_cap')

    if preset and preset in MARKET_CAP_PRESETS and preset != 'all':
        p = MARKET_CAP_PRESETS[preset]
        min_mc = p['min']
        max_mc = p['max']

    result = run_technical_screen(
        list_key=list_key,
        custom_tickers=custom_tickers,
        min_market_cap=min_mc,
        max_market_cap=max_mc,
        offset=offset,
        limit=limit,
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@api_screeners_bp.route('/api/simple-screen', methods=['POST'])
def api_simple_screen():
    """
    Run simple RSI + MACD screening on a stock list.

    POST JSON body:
        list (str): Stock list key or 'custom'
        tickers (list): Custom tickers (if list='custom')
        market_cap_preset (str): Preset key like 'small', 'mid', 'large' (optional)
    """
    data = request.get_json() or {}
    list_key = data.get('list', '').strip()
    custom_tickers = data.get('tickers', [])
    preset = data.get('market_cap_preset', 'all')
    offset = data.get('offset')
    limit = data.get('limit')

    if not list_key:
        return jsonify({'success': False, 'error': 'Parameter "list" is required.'}), 400

    result = run_simple_screen(
        list_key=list_key,
        custom_tickers=custom_tickers,
        market_cap_preset=preset,
        offset=offset,
        limit=limit,
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)
