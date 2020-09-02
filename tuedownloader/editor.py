import subprocess
import ffmpeg

def detect_crop(filepath):
    #b'crop=720:528:120:6\n'
    # TODO: The below command only check the first second to determine the crop.
    # This may not always hold for the entire video
    # 
    # The reason we can't just use the video's dimensions, is that a lot of lectures will use
    # 4:3 slides on a 16:9 stream, leaving black bars all over the place
    #
    # TODO; This uses subprocess/awk instead of relying on ffmpeg-python bindings.
    # Might make it harder to support Windows/Mac
    # Also, this uses 'shell=True', with "filepath" as an injection vector, which is insecure
    crop_string = subprocess.check_output("ffmpeg -i '"+filepath+"' -t 1 -vf cropdetect -f null - 2>&1 | awk '/crop=/ { print substr($NF, 6) }' | tail -1", shell=True).decode('ascii').strip()
    # TODO: Check if crop_string is empty
    print(crop_string)
    dimensions = [int(i) for i in crop_string.split(':')]
    # Width, Heigth, (Top left corner)
    return dimensions

'''
    Takes as input 2 mp4 files and returns a single mp4 file that
    contains both files, side by side, scaled to the same height
    The audio is taken from the second file.
'''
def side_by_side(cam_path, pc_path, out_path, preset='veryfast'):
    cam_crop = detect_crop(cam_path)
    pc_crop = detect_crop(pc_path)

    cam_stream = ffmpeg.input(cam_path).filter('crop', *cam_crop)
    pc_stream = ffmpeg.input(pc_path).filter('crop', *pc_crop)

    # The heights must match for hstack to work
    if cam_crop[1] > pc_crop[1]:
        pc_stream = pc_stream.filter('scale', -1, cam_crop[1])
    elif pc_crop[1] > cam_crop[1]:
        cam_stream = cam_stream.filter('scale', -1, pc_crop[1])

    (
        ffmpeg
        .filter([cam_stream, pc_stream], 'hstack')
        .output(out_path, **{'map': '1:a', 'preset': preset, 'crf': 23})
        .global_args('-threads', '0')
        .run()
    )

'''
    Takes as input 2 mp4 files and returns a single mp4 file that
    contains both files in a diagonal layout
    The audio is taken from the second file.
'''
def diagonal(cam_path, pc_path, out_path, preset='veryfast', overlap=(0, 0)):
    cam_crop = detect_crop(cam_path)
    pc_crop = detect_crop(pc_path)

    cam_stream = ffmpeg.input(cam_path).filter('crop', *cam_crop)
    pc_stream = ffmpeg.input(pc_path).filter('crop', *pc_crop)

    xo, yo = cam_crop[0] - overlap[0], cam_crop[1] - overlap[1]
    layout = '0_0|{}_{}'.format(xo, yo)

    # Calculate the total width/height of the video
    tw = cam_crop[0] + pc_crop[0] - overlap[0]
    th = cam_crop[1] + pc_crop[1] - overlap[1]
    # Pad the stream in the top-left corner to add a black background
    cam_padded = cam_stream.filter('pad', tw, th, 0, 0)

    (
        ffmpeg
        .filter_([cam_padded, pc_stream], 'xstack', layout=layout)
        .output(out_path, **{'map': '1:a', 'preset': preset, 'crf': 23})
        .global_args('-threads', '0')
        .run()
    )
