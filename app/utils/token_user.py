from app.models.model_user import User


def simulate_current_user(user_obj, is_main=True, parent_id=None):
    class SimulatedUser:
        def __init__(self, user_obj, is_main, parent_id):
            self.id = user_obj.id
            self.is_main_user = is_main
            self.parent_user_id = parent_id

    if is_main:
        return SimulatedUser(user_obj, True, None)
    else:
        return SimulatedUser(user_obj, False, parent_id)

def resolve_subscription_owner(user: User) -> int:
    return (
        user.parent_user_id
        if not user.is_main_user
        else user.id
    )
