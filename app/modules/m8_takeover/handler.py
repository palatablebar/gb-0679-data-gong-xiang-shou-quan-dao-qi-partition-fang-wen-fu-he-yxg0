from flask import Blueprint,request,jsonify
from app.errors import DomainError
from app.modules.m8_takeover.rules import resolve_snapshot
bp=Blueprint("takeover",__name__)
@bp.route("/api/takeover",methods=["GET","POST"])
def preview():
    payload=request.get_json(silent=True) if request.method=="POST" else {}
    if payload is None or not isinstance(payload,dict): raise DomainError("BAD_BODY","请求需要对象")
    return jsonify(resolve_snapshot(payload))
