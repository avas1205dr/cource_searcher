import aiohttp
import asyncio
from fake_useragent import UserAgent
from typing import List, Dict
from asgiref.sync import sync_to_async
from django.db import transaction
from datetime import datetime

from parser.models import Category, CourseList, StepikUser, Course, Review

CATEGORIES_NUMS_URL = (
    "https://cdn.stepik.net/media/files/rubricator_prod_20251224.json"
)
COURSE_LISTS_API = "https://stepik.org/api/course-lists"
COURSES_API = "https://stepik.org/api/courses"
REVIEWS_API = "https://stepik.org/api/course-reviews"
USERS_API = "https://stepik.org/api/users"


class StepikParser:
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.session = None
        self.semaphore = None

    def _generate_headers(self) -> Dict[str, str]:
        ua = UserAgent()
        return {"User-Agent": ua.random}

    async def _fetch_json(self, url: str) -> Dict:
        async with self.semaphore:
            headers = self._generate_headers()
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_categories(self) -> tuple[List[int], List[Dict]]:
        async with self.session.get(CATEGORIES_NUMS_URL) as response:
            categories_all = await response.json()

        for subject in categories_all["subjects"]:
            if subject["title"] == "Информационные технологии":
                categories_it_nums = subject["meta_categories"]
                categories_it = [
                    cat
                    for cat in categories_all["meta_categories"]
                    if cat["id"] in categories_it_nums
                ]

                all_course_lists = []
                for category in categories_it:
                    all_course_lists.extend(category.get("course_lists", []))

                return list(set(all_course_lists)), categories_it

        return [], []

    async def get_course_lists(self, course_list_ids: List[int]) -> Dict:
        params = "&".join([f"ids[]={cid}" for cid in course_list_ids])
        url = f"{COURSE_LISTS_API}?{params}"

        try:
            data = await self._fetch_json(url)
            course_lists = data.get("course-lists", [])

            result = {}
            for cl in course_lists:
                title = cl.get("title", "Unknown")
                result[title] = {
                    "id": cl.get("id"),
                    "title": title,
                    "description": cl.get("description", ""),
                    "course_count": len(cl.get("courses", [])),
                    "course_ids": cl.get("courses", []),
                }

            return result
        except Exception as e:
            print(f"Ошибка: {e}")
            return {}

    async def get_course_details(
        self, course_ids: List[int], batch_size: int = 100
    ) -> List[Dict]:
        batches = [
            course_ids[i : i + batch_size]
            for i in range(0, len(course_ids), batch_size)
        ]
        all_courses = []

        for i, batch in enumerate(batches, 1):
            params = "&".join([f"ids[]={cid}" for cid in batch])
            url = f"{COURSES_API}?{params}"

            try:
                data = await self._fetch_json(url)
                courses = data.get("courses", [])
                all_courses.extend(courses)
                print(f"Загружено {len(all_courses)}/{len(course_ids)} курсов")
            except Exception:
                pass

        return all_courses

    async def get_reviews(self, course_id: int) -> List[Dict]:
        url = f"{REVIEWS_API}?course={course_id}"
        try:
            data = await self._fetch_json(url)
            return data.get("course-reviews", [])
        except Exception:
            return []

    async def get_users(self, user_ids: List[int]) -> Dict:
        if not user_ids:
            return {}

        params = "&".join([f"ids[]={uid}" for uid in user_ids])
        url = f"{USERS_API}?{params}"

        try:
            data = await self._fetch_json(url)
            users = data.get("users", [])
            return {user["id"]: user for user in users}
        except Exception:
            return {}

    @sync_to_async
    def save_user_to_db(self, user_data: Dict) -> StepikUser:
        user, created = StepikUser.objects.update_or_create(
            external_id=user_data["id"],
            defaults={
                "full_name": user_data.get("full_name", ""),
                "avatar": user_data.get("avatar", ""),
                "bio": user_data.get("bio", ""),
                "details": user_data,
            },
        )
        return user

    @sync_to_async
    def save_course_list_to_db(
        self, list_data: Dict, category: Category = None
    ) -> CourseList:
        course_list, created = CourseList.objects.update_or_create(
            external_id=list_data["id"],
            defaults={
                "title": list_data["title"],
                "description": list_data.get("description", ""),
                "category": category,
            },
        )
        return course_list

    @sync_to_async
    def save_course_to_db(self, course_data: Dict) -> Course:
        cover = course_data.get("cover", "")
        if not cover or cover == "None":
            cover = ""
        
        course, created = Course.objects.update_or_create(
            external_id=course_data["id"],
            defaults={
                "title": course_data.get("title", ""),
                "slug": course_data.get("slug", ""),
                "description": course_data.get("description", ""),
                "summary": course_data.get("summary", ""),
                "cover": cover,
                "is_paid": course_data.get("is_paid", False),
                "price": course_data.get("price"),
                "learners_count": course_data.get("learners_count", 0),
                "time_to_complete": course_data.get("time_to_complete"),
                "language": course_data.get("language", ""),
                "is_active": course_data.get("is_active", True),
                "is_public": course_data.get("is_public", True),
                "is_featured": course_data.get("is_featured", False),
                "reviews_count": course_data.get("reviews_count", 0),
                "raw_data": course_data,
                "platform": "stepik",
            },
        )
        return course

    @sync_to_async
    def link_course_relations(
        self,
        course: Course,
        course_lists: List[CourseList],
        authors: List[StepikUser],
        instructors: List[StepikUser],
    ):
        if course_lists:
            course.course_lists.set(course_lists)
        if authors:
            course.authors.set(authors)
        if instructors:
            course.instructors.set(instructors)

    @sync_to_async
    def save_review_to_db(
        self, review_data: Dict, course: Course, user: StepikUser = None
    ) -> Review:
        create_date = None
        update_date = None

        if review_data.get("create_date"):
            try:
                create_date = datetime.fromisoformat(
                    review_data["create_date"].replace("Z", "+00:00")
                )
            except:
                pass

        if review_data.get("update_date"):
            try:
                update_date = datetime.fromisoformat(
                    review_data["update_date"].replace("Z", "+00:00")
                )
            except:
                pass

        review, created = Review.objects.update_or_create(
            external_id=review_data["id"],
            defaults={
                "course": course,
                "user": user,
                "score": review_data.get("score", 0),
                "text": review_data.get("text", ""),
                "create_date": create_date,
                "update_date": update_date,
                "raw_data": review_data,
            },
        )
        return review

    async def process_course(
        self, course: Dict, course_list_obj: CourseList
    ) -> None:
        course_id = course.get("id")

        user_ids = set()
        user_ids.update(course.get("authors", []))
        user_ids.update(course.get("instructors", []))

        reviews = await self.get_reviews(course_id)

        for review in reviews:
            if review.get("user"):
                user_ids.add(review.get("user"))

        users_info = await self.get_users(list(user_ids))

        users_db = {}
        for user_id, user_data in users_info.items():
            user_obj = await self.save_user_to_db(user_data)
            users_db[user_id] = user_obj

        course_obj = await self.save_course_to_db(course)

        authors = [
            users_db[uid] for uid in course.get("authors", []) if uid in users_db
        ]
        instructors = [
            users_db[uid]
            for uid in course.get("instructors", [])
            if uid in users_db
        ]

        await self.link_course_relations(
            course_obj, [course_list_obj], authors, instructors
        )

        for review in reviews:
            user = users_db.get(review.get("user"))
            await self.save_review_to_db(review, course_obj, user)

    async def save_courses(
        self,
        courses: List[Dict],
        list_name: str,
        list_data: Dict,
        category: Category,
        processed_ids: set,
    ) -> int:
        new_courses = [c for c in courses if c.get("id") not in processed_ids]

        if not new_courses:
            print(f"\nПропущено: {list_name} (все курсы уже обработаны)")
            return 0

        print(
            f"\nОбработка категории: {list_name} ({len(new_courses)} новых из {len(courses)})"
        )

        course_list_obj = await self.save_course_list_to_db(list_data, category)

        for i, course in enumerate(new_courses, 1):
            course_id = course.get("id")
            try:
                await self.process_course(course, course_list_obj)
                processed_ids.add(course_id)

                if i % 10 == 0 or i == len(new_courses):
                    print(
                        f"{list_name}: {i}/{len(new_courses)} курсов обработано"
                    )
            except Exception as e:
                print(f"Ошибка при обработке курса {course_id}: {e}")

        print(f"Завершено: {list_name}")
        return len(new_courses)

    @sync_to_async
    def save_category_to_db(self, category_data: Dict) -> Category:
        category, created = Category.objects.update_or_create(
            external_id=category_data["id"],
            defaults={
                "title": category_data.get("title", ""),
            },
        )
        return category

    async def parse(self):
        connector = aiohttp.TCPConnector(limit=50)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            self.session = session
            self.semaphore = asyncio.Semaphore(self.max_concurrent)

            course_list_ids, categories = await self.get_categories()
            if not course_list_ids:
                return None, None

            print(f"Найдено {len(categories)} категорий")

            categories_db = {}
            for cat_data in categories:
                cat_obj = await self.save_category_to_db(cat_data)
                categories_db[cat_data["id"]] = cat_obj

            courses_by_lists = await self.get_course_lists(course_list_ids)

            all_unique_course_ids = set()
            for info in courses_by_lists.values():
                all_unique_course_ids.update(info["course_ids"])

            print(f"Уникальных курсов: {len(all_unique_course_ids)}\n")

            course_details = await self.get_course_details(
                list(all_unique_course_ids)
            )
            print(f"\nПолучено деталей: {len(course_details)} курсов")

            course_by_id = {c["id"]: c for c in course_details}

            processed_course_ids = set()
            total_processed = 0

            for list_name, info in courses_by_lists.items():
                category = None
                for cat_data in categories:
                    if info["id"] in cat_data.get("course_lists", []):
                        category = categories_db[cat_data["id"]]
                        break

                category_courses = [
                    course_by_id[cid]
                    for cid in info["course_ids"]
                    if cid in course_by_id
                ]
                if category_courses:
                    processed = await self.save_courses(
                        category_courses,
                        list_name,
                        info,
                        category,
                        processed_course_ids,
                    )
                    total_processed += processed

            print(f"\n{'='*60}")
            print(f"Всего обработано уникальных курсов: {total_processed}")

            return courses_by_lists, all_unique_course_ids


async def main():
    parser = StepikParser(max_concurrent=7)
    courses_data, course_ids = await parser.parse()
    return courses_data, course_ids


if __name__ == "__main__":
    courses_data, course_ids = asyncio.run(main())