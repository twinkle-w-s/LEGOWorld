"""Disposable native/script worker. JSON files carry results; stdout is only a log."""

import base64
import io
import json
import os
from pathlib import Path
import runpy
import sys
import traceback


def execute(request):
    from legoworld.backend import b, pack, unpack
    from legoworld.editing import apply_operations, integrate
    from legoworld.precision import validate_document
    document = request["document"]
    action = request["action"]
    if action in ("build", "edit", "import"):
        details = {}
        if action == "build":
            source = Path(request["path"])
            sys.path.insert(0, str(source.parent))
            namespace = runpy.run_path(str(source), run_name="legoworld_build")
            component = namespace["build"](**request.get("parameters", {}))
            document, details = integrate(document, component, request["mode"], request["target_id"],
                                          request.get("pose"), request.get("mount"))
            sources = {str(source.relative_to(Path(request["workspace"]))): source.read_text(encoding="utf-8")}
            for module in tuple(sys.modules.values()):
                filename = getattr(module, "__file__", None)
                if filename:
                    path = Path(filename).resolve()
                    if path.suffix == ".py" and path.is_relative_to(source.parent) and path.is_file():
                        sources[str(path.relative_to(Path(request["workspace"])))] = path.read_text(encoding="utf-8")
            document["recipes"].append({"path": str(source), "parameters": request.get("parameters", {}),
                "mode": request["mode"], "target_id": request["target_id"], "sources": sources})
        elif action == "edit":
            document, details = apply_operations(document, request["operations"])
        else:
            from legoworld.studio_io import read_model
            source = Path(request["path"])
            document = json.loads(source.read_text(encoding="utf-8")) if source.suffix.lower() == ".json" else pack(read_model(source))
        document["revision"] = request["document"]["revision"] + 1
        report = validate_document(document)
        return {"ok": report["batch_valid"], "document": document, "validation": report, "details": details}
    if action == "validate":
        return {"ok": True, "validation": validate_document(document, request.get("stability", False))}
    if action == "export":
        report = validate_document(document, True)
        return {"ok": report["exportable"], "validation": report,
                "mpd_text": b.ldraw(unpack(document)) if report["exportable"] else None}
    if action == "render":
        from legoworld.geometry import render_png
        from PIL import Image, ImageDraw
        if request.get("four_views"):
            sheet = Image.new("RGB", (1200, 940), (245, 245, 248))
            for i, angle in enumerate((0, 90, 180, 270)):
                png = render_png(document, azimuth=angle, node_ids=request.get("node_ids"))
                x, y = i % 2 * 600, i // 2 * 470
                with Image.open(io.BytesIO(png)) as picture:
                    sheet.paste(picture, (x, y + 25))
                ImageDraw.Draw(sheet).text((x + 12, y + 8), f"View {i+1} / azimuth {angle}", fill=(45, 50, 60))
            stream = io.BytesIO()
            sheet.save(stream, format="PNG")
            png = stream.getvalue()
        else:
            png = render_png(document, request.get("azimuth", 35), request.get("elevation", 28),
                             900, 650, request.get("node_ids"))
        return {"ok": True, "png": base64.b64encode(png).decode("ascii")}
    raise ValueError(f"Unknown worker action {action!r}")


def main():
    request_path, response_path = map(Path, sys.argv[1:3])
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        from legoworld.assets import collider_root
        os.environ["BRICKNET_DATA"] = str(collider_root().resolve())
        result = execute(request)
    except Exception as error:
        result = {"ok": False, "error": {"type": type(error).__name__, "message": str(error),
                                       "traceback": traceback.format_exc()}}
    response_path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
