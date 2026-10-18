import asyncio
from app.database import SessionLocal
from app.services.property_reminder_service import dispatch_property_reminders


async def main():
    db=SessionLocal()
    try:
        result=await dispatch_property_reminders(db)
        print(result)
    finally:
        db.close()


if __name__=="__main__":
    asyncio.run(main())
