"""
Tool cat video thanh nhieu canh (scene) rieng biet.
Tu dong phat hien diem chuyen canh va xuat moi canh thanh 1 file video.

Dung khong tham so de mo menu tuong tac:
    python cat_canh.py

Hoac dung truc tiep qua dong lenh (khong mo menu):
    python cat_canh.py video.mp4
    python cat_canh.py video.mp4 --do-nhay 27 --thu-muc ket_qua
    python cat_canh.py video.mp4 --canh-toi-thieu 1.0

Tham so:
    video               Duong dan file video dau vao
    --do-nhay            Nguong phat hien chuyen canh (mac dinh 46).
                          So nho hon -> nhay cam hon, cat ra nhieu canh hon.
    --canh-toi-thieu     Do dai toi thieu 1 canh, tinh bang giay (mac dinh 0.6s)
    --thu-muc            Thu muc luu cac video da cat (mac dinh: <ten_video>_canh)
    --trim               Cat bot dau/cuoi moi canh, tinh bang giay (mac dinh 0, tat).
                          Chi bat khi video co hieu ung chuyen canh mem (dissolve/crossfade)
                          khien vai frame dau/cuoi bi lan sang canh ben canh.
"""

import argparse
import sys
from pathlib import Path

from scenedetect import open_video, SceneManager, split_video_ffmpeg
from scenedetect.detectors import ContentDetector


def cat_video_theo_canh(duong_dan_video: str, do_nhay: float, canh_toi_thieu_giay: float, thu_muc_ra: str, trim_giay: float = 0.0):
    duong_dan_video = Path(duong_dan_video)
    if not duong_dan_video.exists():
        print(f"Khong tim thay file: {duong_dan_video}")
        sys.exit(1)

    thu_muc_ra = Path(thu_muc_ra)
    thu_muc_ra.mkdir(parents=True, exist_ok=True)

    print(f"Dang phan tich video: {duong_dan_video}")
    video = open_video(str(duong_dan_video))
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(
            threshold=do_nhay,
            min_scene_len=int(canh_toi_thieu_giay * video.frame_rate),
        )
    )

    scene_manager.detect_scenes(video, show_progress=True)
    danh_sach_canh = scene_manager.get_scene_list()

    if not danh_sach_canh:
        print("Khong phat hien duoc canh nao (video co the chi co 1 canh duy nhat).")
        return

    if trim_giay > 0:
        danh_sach_canh_moi = []
        for bat_dau, ket_thuc in danh_sach_canh:
            do_dai_giay = (ket_thuc - bat_dau).get_seconds()
            trim_thuc_te = min(trim_giay, do_dai_giay / 3)
            danh_sach_canh_moi.append((bat_dau + trim_thuc_te, ket_thuc - trim_thuc_te))
        danh_sach_canh = danh_sach_canh_moi

    print(f"Phat hien {len(danh_sach_canh)} canh. Dang cat video...")

    ten_goc = duong_dan_video.stem
    mau_ten_file = f"{ten_goc}-Canh-$SCENE_NUMBER.mp4"

    split_video_ffmpeg(
        str(duong_dan_video),
        danh_sach_canh,
        output_dir=str(thu_muc_ra),
        output_file_template=mau_ten_file,
        show_progress=True,
    )

    print(f"\nHoan tat! Da luu {len(danh_sach_canh)} video canh vao thu muc: {thu_muc_ra.resolve()}")
    for i, (bat_dau, ket_thuc) in enumerate(danh_sach_canh, start=1):
        print(f"  Canh {i:02d}: {bat_dau.get_timecode()} -> {ket_thuc.get_timecode()}")


# ---------------------------------------------------------------------------
# Menu tuong tac (khi chay khong tham so)
# ---------------------------------------------------------------------------

def _nhap_so(nhac: str, mac_dinh: float) -> float:
    raw = input(f"{nhac} (mac dinh {mac_dinh}): ").strip()
    if not raw:
        return mac_dinh
    try:
        return float(raw)
    except ValueError:
        print(f"  Gia tri khong hop le, dung mac dinh {mac_dinh}.")
        return mac_dinh


def _nhap_duong_dan_video() -> Path | None:
    raw = input("Duong dan file video (de trong de quay lai menu): ").strip().strip('"')
    if not raw:
        return None
    duong_dan = Path(raw)
    if not duong_dan.exists():
        print(f"  Khong tim thay file: {duong_dan}")
        return _nhap_duong_dan_video()
    return duong_dan


def _chay_tac_vu_cat_canh():
    duong_dan_video = _nhap_duong_dan_video()
    if duong_dan_video is None:
        return

    do_nhay = _nhap_so("Do nhay phat hien chuyen canh (nho hon = nhay cam hon)", 46.0)
    canh_toi_thieu = _nhap_so("Do dai toi thieu moi canh (giay)", 0.6)
    trim = _nhap_so("Cat bot dau/cuoi moi canh (giay, 0 = tat)", 0.0)

    mac_dinh_thu_muc = f"{duong_dan_video.stem}_canh"
    thu_muc_ra = input(f"Thu muc luu ket qua (mac dinh {mac_dinh_thu_muc}): ").strip()
    if not thu_muc_ra:
        thu_muc_ra = mac_dinh_thu_muc

    print()
    try:
        cat_video_theo_canh(str(duong_dan_video), do_nhay, canh_toi_thieu, thu_muc_ra, trim)
    except Exception as loi:
        print(f"Co loi xay ra: {loi}")
    print()


def chay_menu():
    while True:
        print("=" * 50)
        print("  TOOL CAT VIDEO THEO CANH (SCENE)")
        print("=" * 50)
        print("  1. Cat 1 video theo canh")
        print("  0. Thoat")
        lua_chon = input("Chon: ").strip()

        if lua_chon == "1":
            _chay_tac_vu_cat_canh()
        elif lua_chon == "0":
            print("Tam biet!")
            return
        else:
            print("Lua chon khong hop le, thu lai.\n")


def main():
    if len(sys.argv) == 1:
        chay_menu()
        return

    parser = argparse.ArgumentParser(description="Cat video thanh nhieu canh rieng biet theo tung scene.")
    parser.add_argument("video", help="Duong dan file video dau vao")
    parser.add_argument("--do-nhay", type=float, default=46.0, help="Nguong phat hien chuyen canh (mac dinh 46, cang nho cang nhay)")
    parser.add_argument("--canh-toi-thieu", type=float, default=0.6, help="Do dai toi thieu moi canh, giay (mac dinh 0.6)")
    parser.add_argument("--thu-muc", default=None, help="Thu muc luu ket qua")
    parser.add_argument("--trim", type=float, default=0.0, help="Cat bot dau/cuoi moi canh, giay (mac dinh 0, tat)")

    args = parser.parse_args()

    thu_muc_ra = args.thu_muc or f"{Path(args.video).stem}_canh"
    cat_video_theo_canh(args.video, args.do_nhay, args.canh_toi_thieu, thu_muc_ra, args.trim)


if __name__ == "__main__":
    main()
