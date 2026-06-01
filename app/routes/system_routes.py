from flask import Blueprint, jsonify

from app.services.system_service import SystemMonitorService

system_bp = Blueprint(
    'system',
    __name__,
    url_prefix='/api/system'
)


@system_bp.route('/status', methods=['GET'])
def system_status():

    data = SystemMonitorService.get_system_info()

    return jsonify({
        "success": True,
        "data": data
    })