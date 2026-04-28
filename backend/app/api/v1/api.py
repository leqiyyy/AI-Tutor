from fastapi import APIRouter

from app.api.v1 import admin, analytics, auth, chat, classes, courses, flashcards, frontend_compat, kb, notifications, recommendations, reviews, students, tasks, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(courses.router)
api_router.include_router(classes.router)
api_router.include_router(frontend_compat.router)
api_router.include_router(kb.router)
api_router.include_router(tasks.router)
api_router.include_router(flashcards.router)
api_router.include_router(chat.router)
api_router.include_router(reviews.router)
api_router.include_router(recommendations.router)
api_router.include_router(analytics.router)
api_router.include_router(students.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
