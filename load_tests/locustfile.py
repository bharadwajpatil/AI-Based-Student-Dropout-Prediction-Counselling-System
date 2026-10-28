"""
Beacon Academic Early Warning System - Load & Stress Testing Suite
Locust configuration for simulating 500 concurrent dashboard users,
faculty grading queries, and background import load.
"""

import json
import random
from locust import HttpUser, task, between, events


class BeaconUser(HttpUser):
    wait_time = between(1, 3)  # Human think-time between actions
    token = None
    headers = {}
    student_ids = []

    def on_start(self):
        """Authenticate user on virtual user spawn."""
        # Log in as teacher/faculty
        payload = {
            "email": "faculty.loadtest@institution.edu",
            "password": "Password@123",
        }
        res = self.client.post("/api/v1/auth/login", json=payload)
        if res.status_code == 200:
            data = res.json()
            self.token = data.get("access_token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        else:
            # Fallback mock header for direct synthetic load test against mock server
            self.headers = {"Content-Type": "application/json"}

    @task(4)
    def view_dashboard_overview(self):
        """Simulate frequent dashboard KPI aggregation polling (single-pass $facet)."""
        self.client.get(
            "/api/v1/analytics/overview",
            headers=self.headers,
            name="/analytics/overview (KPI Dashboard)",
        )

    @task(3)
    def view_risk_distribution(self):
        """Simulate loading risk distribution charts."""
        self.client.get(
            "/api/v1/analytics/distribution",
            headers=self.headers,
            name="/analytics/distribution",
        )

    @task(3)
    def list_students_roster(self):
        """Simulate paginated student cohort search."""
        params = {"limit": 20, "search": random.choice(["", "Rahul", "Priya", "Kumar", "CS"])}
        res = self.client.get(
            "/api/v1/students",
            headers=self.headers,
            params=params,
            name="/students?limit=20&search=*",
        )
        if res.status_code == 200:
            try:
                items = res.json().get("items", [])
                if items:
                    self.student_ids = [s["id"] for s in items]
            except Exception:
                pass

    @task(2)
    def view_student_detail_and_risk(self):
        """Simulate clicking a student to view factor breakdown."""
        if self.student_ids:
            sid = random.choice(self.student_ids)
            self.client.get(
                f"/api/v1/students/{sid}",
                headers=self.headers,
                name="/students/[id] (Profile)",
            )
            self.client.get(
                f"/api/v1/students/{sid}/risk",
                headers=self.headers,
                name="/students/[id]/risk (Factor Breakdown)",
            )

    @task(1)
    def export_high_risk_report(self):
        """Simulate downloading the formula-neutralized CSV report."""
        self.client.get(
            "/api/v1/analytics/export/high-risk",
            headers=self.headers,
            name="/analytics/export/high-risk (CSV Download)",
        )

    @task(1)
    def check_unread_notifications(self):
        """Simulate notification center polling / sync."""
        self.client.get(
            "/api/v1/notifications/unread-count",
            headers=self.headers,
            name="/notifications/unread-count",
        )
