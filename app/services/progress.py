from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo


async def get_debt_progress(session: AsyncSession, user_id: int):
    obligations = await obligations_repo.list_active_by_user(session, user_id)
    total_paid = await payments_repo.sum_paid_by_user(session, user_id)
    items = []
    total_debt = 0
    has_unknown = False
    for obligation in obligations:
        paid = await payments_repo.sum_paid_for_obligation(session, obligation.id)
        if obligation.total_debt_amount is None:
            has_unknown = True
        else:
            total_debt += obligation.total_debt_amount
        items.append({"title": obligation.title, "total_debt_amount": obligation.total_debt_amount, "paid_amount": paid})
    return {"total_debt": total_debt, "total_paid": total_paid, "items": items, "has_unknown_debts": has_unknown}
