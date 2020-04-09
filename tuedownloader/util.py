OTHER_ALLOWED = ' -_.'


def _escape_fs_path(insecure_name):
    return ''.join(
            x for x in insecure_name if (
                x.isalnum() or x in OTHER_ALLOWED)
            )


def escape_dir(insecure_dirname):
    return _escape_fs_path(insecure_dirname)


def escape_file(insecure_filename):
    return _escape_fs_path(insecure_filename)
