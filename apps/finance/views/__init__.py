# Re-export shared util and all views from the legacy module so urls.py can keep "from . import views"
from apps.finance.views.common import prepare_transactions_for_session  # noqa: F401
from apps.finance.views_legacy import *  # noqa: F401, F403
