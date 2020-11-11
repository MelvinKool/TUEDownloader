import re
import ffmpeg
import tempfile

def detect_crop(filepath):
    # TODO: The below command only check the first second to determine the crop.
    # This may not always hold for the entire video
    # 
    # The reason we can't just use the video's dimensions, is that a lot of lectures will use
    # 4:3 slides on a 16:9 stream, leaving black bars all over the place

    # FFMPEG uses stderr to print the revevant info

    throwaway_file = tempfile.NamedTemporaryFile()
    _, std_err_dump = ffmpeg.input(
                filepath, ss=1
            ).filter(
                'cropdetect'
            ).output(
                throwaway_file.name, vframes=2
            ).overwrite_output(
            ).run(
                capture_stdout=True,
                capture_stderr=True
            )


    # We're looking for the last occurrence of "crop=720:528:120:6"
    crop_string = re.findall(b"crop=\d+:\d+:\d+:\d+", std_err_dump)[-1]

    # Skip "crop=" and split the rest
    dimensions = [int(i) for i in crop_string[5:].split(b':')]

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
