from .services import profile_update_context


def usuario_profile_state(request):
    return profile_update_context(request)

