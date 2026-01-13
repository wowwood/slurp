def format_duration(seconds: int) -> str:
    """format_duration nicely formats the given duration in seconds.
    :param seconds: the duration in seconds
    :return str: The duration formatted nicely, in hours, minutes, and seconds.
    """
    seconds = int(seconds)

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " ".join(parts)
