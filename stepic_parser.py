import aiohttp
import asyncio
from fake_useragent import UserAgent
import json
import os
from typing import List, Dict

CATEGORIES_NUMS_URL = "https://cdn.stepik.net/media/files/rubricator_prod_20251224.json"
COURSE_LISTS_API = "https://stepik.org/api/course-lists"
COURSES_API = "https://stepik.org/api/courses"
REVIEWS_API = "https://stepik.org/api/course-reviews"
USERS_API = "https://stepik.org/api/users"

class StepikParser:
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.session = None
        self.output_dir = "courses_data"
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
                categories_it = [cat for cat in categories_all["meta_categories"] 
                               if cat["id"] in categories_it_nums]
                
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
                    "course_ids": cl.get("courses", [])
                }
            
            return result
        except Exception as e:
            print(f"Ошибка: {e}")
            return {}
    
    async def get_course_details(self, course_ids: List[int], batch_size: int = 100) -> List[Dict]:
        batches = [course_ids[i:i+batch_size] for i in range(0, len(course_ids), batch_size)]
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
    
    async def process_course(self, course: Dict, category_name: str) -> None:
        course_id = course.get("id")
        
        user_ids = set()
        user_ids.update(course.get("authors", []))
        user_ids.update(course.get("instructors", []))
        
        reviews = await self.get_reviews(course_id)
        
        for review in reviews:
            user_ids.add(review.get("user"))
        
        users_info = await self.get_users(list(user_ids))
        
        course_data = {
            "course": course,
            "reviews": reviews,
            "users": users_info,
            "category": category_name
        }
        
        filename = os.path.join(self.output_dir, f"course_{course_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(course_data, f, ensure_ascii=False, indent=2)
    
    async def save_courses(self, courses: List[Dict], category_name: str) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"\nОбработка категории: {category_name} ({len(courses)} курсов)")
        
        for i, course in enumerate(courses, 1):
            await self.process_course(course, category_name)
            if i % 10 == 0 or i == len(courses):
                print(f"  {category_name}: {i}/{len(courses)} курсов обработано")
        
        print(f"Завершено: {category_name}")
    
    async def parse(self):
        connector = aiohttp.TCPConnector(limit=50)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            self.session = session
            self.semaphore = asyncio.Semaphore(self.max_concurrent)
            
            course_list_ids, categories = await self.get_categories()
            if not course_list_ids:
                return None, None
            
            print(f"Найдено {len(categories)} категорий")
            
            courses_by_lists = await self.get_course_lists(course_list_ids)
            
            all_unique_course_ids = set()
            for info in courses_by_lists.values():
                all_unique_course_ids.update(info["course_ids"])
            
            print(f"Уникальных курсов: {len(all_unique_course_ids)}\n")
            
            course_details = await self.get_course_details(list(all_unique_course_ids))
            print(f"\nПолучено деталей: {len(course_details)} курсов")
            
            course_by_id = {c["id"]: c for c in course_details}
            
            for list_name, info in courses_by_lists.items():
                category_courses = [course_by_id[cid] for cid in info["course_ids"] if cid in course_by_id]
                if category_courses:
                    await self.save_courses(category_courses, list_name)
            
            print(f"\n{'='*60}")
            print(f"Сохранено {len(course_details)} курсов в '{self.output_dir}'")
            
            return courses_by_lists, all_unique_course_ids


async def main():
    parser = StepikParser(max_concurrent=7)
    courses_data, course_ids = await parser.parse()
    return courses_data, course_ids


if __name__ == "__main__":
    courses_data, course_ids = asyncio.run(main())