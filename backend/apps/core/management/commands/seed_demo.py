"""Seed ClientFlow CRM with a fictional demo dataset.

Everything here is invented: company names, people, e-mail addresses (reserved `.example` domains)
and phone numbers (the 555-01xx range reserved for fiction). No real people or businesses.
"""

import os
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.activities.models import Interaction, Notification, Task
from apps.automation import rules
from apps.crm.models import Company, Contact, Tag
from apps.sales import services
from apps.sales.models import Deal, DealStageHistory, Lead

DEMO_USERS = [
    # username, first, last, role
    ("admin", "Morgan", "Ellis", Role.ADMIN),
    ("manager", "Jordan", "Rivera", Role.MANAGER),
    ("rep", "Taylor", "Brooks", Role.SALES_REP),
    ("rep2", "Casey", "Nguyen", Role.SALES_REP),
]

COMPANIES = [
    ("Alder & Finch Landscaping", "Landscaping", "Portland", "alderfinch"),
    ("Brightwave Dental Studio", "Healthcare", "Austin", "brightwavedental"),
    ("Cedarline Logistics", "Logistics", "Denver", "cedarline"),
    ("Dovetail Interiors", "Interior design", "Seattle", "dovetailinteriors"),
    ("Evergreen Home Services", "Home services", "Raleigh", "evergreenhome"),
    ("Fernhill Veterinary Clinic", "Veterinary", "Madison", "fernhillvet"),
    ("Granite Peak Accounting", "Accounting", "Boise", "granitepeak"),
    ("Harborview Property Management", "Real estate", "San Diego", "harborviewpm"),
    ("Ironbridge Fitness", "Fitness", "Pittsburgh", "ironbridgefit"),
    ("Juniper Lane Bakery", "Food & beverage", "Asheville", "juniperlane"),
    ("Keystone Legal Partners", "Legal services", "Philadelphia", "keystonelegal"),
    ("Lumen Photography Studio", "Creative services", "Nashville", "lumenphoto"),
]

PEOPLE = [
    ("Priya", "Raman", "Owner"),
    ("Marcus", "Webb", "Operations Manager"),
    ("Elena", "Fischer", "Practice Manager"),
    ("Devon", "Okafor", "Office Manager"),
    ("Hannah", "Lindqvist", "Founder"),
    ("Tomás", "Herrera", "Director"),
    ("Aisha", "Khan", "Managing Partner"),
    ("Liam", "O'Donnell", "General Manager"),
    ("Sofia", "Marchetti", "Owner"),
    ("Noah", "Whitfield", "Operations Lead"),
    ("Grace", "Tanaka", "Studio Manager"),
    ("Owen", "Pritchard", "Partner"),
    ("Maya", "Castellanos", "Owner"),
    ("Ethan", "Brandt", "Finance Manager"),
    ("Chloe", "Duval", "Marketing Lead"),
    ("Isaac", "Abernathy", "Co-founder"),
    ("Zara", "Mendel", "Clinic Director"),
    ("Felix", "Kowalski", "Branch Manager"),
    ("Leah", "Strand", "Principal"),
    ("Rohan", "Mehta", "Owner"),
    ("Nora", "Calloway", "Events Coordinator"),
    ("Julian", "Park", "Head of Operations"),
    ("Ivy", "Montgomery", "Owner"),
    ("Callum", "Reid", "Director"),
]

TAGS = [
    ("VIP", "#7c3aed"),
    ("Decision maker", "#0369a1"),
    ("Referral partner", "#047857"),
    ("Newsletter", "#b45309"),
    ("Needs follow-up", "#b91c1c"),
]

DEAL_TEMPLATES = [
    "Website refresh",
    "CRM setup & training",
    "Quarterly service plan",
    "Booking system integration",
    "Email automation package",
    "Annual maintenance contract",
    "Customer portal",
    "Brand & signage package",
    "Reporting dashboard",
    "Onboarding workflow automation",
]
LOST_REASONS = [
    "Chose a cheaper competitor",
    "Budget frozen this quarter",
    "Project postponed to next year",
    "Went with an in-house solution",
]
LEAD_SOURCES = [s for s, _ in Lead.Source.choices]


class Command(BaseCommand):
    help = "Populate the database with fictional demo data (users, companies, contacts, leads, deals, tasks)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing CRM data and demo users first.")
        parser.add_argument("--yes-i-am-sure", action="store_true", help="Allow --reset when DJANGO_DEBUG is off.")

    def handle(self, *args, **opts):
        if opts["reset"]:
            if not settings.DEBUG and not opts["yes_i_am_sure"]:
                raise CommandError("Refusing to --reset with DJANGO_DEBUG off. Re-run with --yes-i-am-sure to confirm.")
            self._reset()
        elif User.objects.filter(username__in=[u[0] for u in DEMO_USERS]).exists():
            raise CommandError("Demo users already exist. Run with --reset to rebuild the demo dataset.")

        rng = random.Random(42)  # deterministic dataset
        password = os.getenv("DEMO_PASSWORD", "ClientFlow-Demo-2026")
        with transaction.atomic():
            users = self._users(password)
            tags = [Tag.objects.create(name=n, color=c) for n, c in TAGS]
            companies = self._companies(rng, users)
            contacts = self._contacts(rng, companies, tags, users)
            self._leads(rng, users)
            self._deals(rng, companies, contacts, users)
            self._interactions(rng, contacts, users)
            self._tasks(rng, contacts, users)
            self._notifications(users)

        counts = {
            "users": User.objects.count(),
            "companies": Company.objects.count(),
            "contacts": Contact.objects.count(),
            "leads": Lead.objects.count(),
            "deals": Deal.objects.count(),
            "tasks": Task.objects.count(),
            "interactions": Interaction.objects.count(),
        }
        self.stdout.write(self.style.SUCCESS("Demo data created: " + ", ".join(f"{v} {k}" for k, v in counts.items())))
        self.stdout.write("Demo logins (fictional accounts):")
        for username, _, _, role in DEMO_USERS:
            self.stdout.write(f"  {username:<8} role={role.value:<9} password={password}")

    # ------------------------------------------------------------------
    def _reset(self):
        with transaction.atomic():
            for model in (Interaction, Task, Notification, DealStageHistory, Deal, Lead, Contact, Company, Tag):
                model.objects.all().delete()
            User.objects.filter(username__in=[u[0] for u in DEMO_USERS]).delete()
        self.stdout.write("Existing CRM data removed.")

    def _users(self, password):
        users = {}
        for username, first, last, role in DEMO_USERS:
            users[username] = User.objects.create_user(
                username=username,
                email=f"{username}@clientflow.example",
                password=password,
                first_name=first,
                last_name=last,
                role=role,
            )
        return users

    def _companies(self, rng, users):
        reps = [users["rep"], users["rep2"], users["manager"]]
        out = []
        for i, (name, industry, city, slug) in enumerate(COMPANIES):
            out.append(
                Company.objects.create(
                    name=name,
                    industry=industry,
                    city=city,
                    country="United States",
                    website=f"https://www.{slug}.example",
                    email=f"hello@{slug}.example",
                    phone=f"+1 555-01{10 + i:02d}",
                    address=f"{100 + i * 7} Market Street",
                    notes="Fictional demo company." if i else "Fictional demo company. Prefers email over phone.",
                    owner=reps[i % len(reps)],
                )
            )
        return out

    def _contacts(self, rng, companies, tags, users):
        out = []
        owners = [users["rep"], users["rep2"]]
        for i, (first, last, title) in enumerate(PEOPLE):
            company = companies[i % len(companies)]
            slug = company.website.split("www.")[1].split(".example")[0]
            contact = Contact.objects.create(
                first_name=first,
                last_name=last,
                job_title=title,
                company=company,
                email=f"{first.lower().replace('á', 'a')}.{last.lower().replace(chr(39), '')}@{slug}.example",
                phone=f"+1 555-01{40 + i:02d}",
                owner=owners[i % 2],
            )
            contact.tags.set(rng.sample(tags, k=rng.choice([0, 1, 1, 2])))
            out.append(contact)
        return out

    def _leads(self, rng, users):
        today = timezone.localdate()
        rows = [
            ("Aaron", "Whitlock", "Whitlock Roofing", "website", "new", -6, 4500),
            ("Bianca", "Soto", "Soto Catering", "referral", "contacted", -3, 6200),
            ("Caleb", "Fraser", "Fraser Auto Detailing", "cold_outreach", "new", -1, 3100),
            ("Dara", "Kelleher", "Kelleher Yoga Collective", "social", "qualified", 2, 8800),
            ("Emil", "Novak", "Novak Cabinetry", "event", "contacted", 3, 12500),
            ("Farah", "Aziz", "Aziz Tutoring Centre", "website", "new", 1, 2400),
            ("Gideon", "Park", "Park & Pine Realty", "partner", "qualified", 5, 15000),
            ("Hollis", "Greer", "Greer Plumbing", "referral", "new", 7, 5200),
            ("Imani", "Duncan", "Duncan Wellness", "website", "contacted", -9, 3900),
            ("Jonah", "Lindgren", "Lindgren Bikes", "event", "unqualified", -12, 1800),
            ("Kira", "Valdez", "Valdez Floral Design", "social", "new", 4, 2700),
            ("Lucas", "Moreau", "Moreau Wine Bar", "cold_outreach", "contacted", 9, 7400),
            ("Mina", "Sato", "Sato Print Shop", "website", "qualified", -2, 5600),
            ("Nolan", "Beck", "Beck Electrical", "partner", "new", 6, 9100),
        ]
        owners = [users["rep"], users["rep2"], users["rep"], users["manager"]]
        for i, (first, last, company, source, status, offset, value) in enumerate(rows):
            Lead.objects.create(  # post_save rule creates the follow-up task
                first_name=first,
                last_name=last,
                company_name=company,
                source=source,
                status=status,
                email=f"{first.lower()}@{company.split()[0].lower()}.example",
                phone=f"+1 555-01{70 + i:02d}",
                owner=owners[i % len(owners)],
                follow_up_date=today + timedelta(days=offset),
                estimated_value=value,
                notes="Fictional demo lead.",
            )

    def _deals(self, rng, companies, contacts, users):
        today = timezone.localdate()
        owners = [users["rep"], users["rep2"], users["manager"]]
        targets = [
            "new",
            "new",
            "qualified",
            "qualified",
            "qualified",
            "proposal",
            "proposal",
            "proposal",
            "negotiation",
            "negotiation",
            "negotiation",
            "won",
            "won",
            "won",
            "lost",
            "lost",
        ]
        path = {
            "new": [],
            "qualified": ["qualified"],
            "proposal": ["qualified", "proposal"],
            "negotiation": ["qualified", "proposal", "negotiation"],
            "won": ["qualified", "proposal", "negotiation", "won"],
            "lost": ["qualified", "lost"],
        }
        for i, target in enumerate(targets):
            company = companies[i % len(companies)]
            company_contacts = [c for c in contacts if c.company_id == company.id]
            owner = owners[i % len(owners)]
            deal = services.create_deal(
                actor=owner,
                title=f"{DEAL_TEMPLATES[i % len(DEAL_TEMPLATES)]} - {company.name.split()[0]}",
                amount=rng.choice([2400, 3800, 5200, 7500, 9800, 12000, 18500, 24000, 36500, 45000]),
                expected_close_date=today + timedelta(days=rng.randint(-10, 60)),
                owner=owner,
                company=company,
                contact=company_contacts[0] if company_contacts else None,
            )
            for step in path[target]:
                reason = rng.choice(LOST_REASONS) if step == "lost" else ""
                services.change_deal_stage(deal, step, actor=owner, lost_reason=reason)
        # a couple of manager-driven moves so reps have stage-change notifications to read
        for deal in Deal.objects.filter(owner=users["rep"], stage="qualified")[:1]:
            services.change_deal_stage(deal, "proposal", actor=users["manager"])

    def _interactions(self, rng, contacts, users):
        now = timezone.now()
        subjects = {
            Interaction.Type.CALL: ["Discovery call", "Pricing questions", "Check-in call", "Scheduling follow-up"],
            Interaction.Type.MEETING: ["On-site walkthrough", "Proposal review", "Kickoff meeting"],
            Interaction.Type.EMAIL: ["Sent proposal", "Sent case overview", "Replied to questions"],
            Interaction.Type.NOTE: [
                "Prefers morning calls",
                "Budget approved pending sign-off",
                "Mentioned expansion plans",
            ],
        }
        authors = [users["rep"], users["rep2"], users["manager"]]
        for i in range(28):
            kind = rng.choice(list(subjects))
            contact = contacts[i % len(contacts)]
            Interaction.objects.create(
                type=kind,
                subject=rng.choice(subjects[kind]),
                notes="Fictional demo interaction.",
                occurred_at=now - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 8)),
                contact=contact,
                company=contact.company,
                created_by=authors[i % len(authors)],
                deal=Deal.objects.filter(company=contact.company).first() if i % 3 == 0 else None,
            )

    def _tasks(self, rng, contacts, users):
        today = timezone.localdate()
        specs = [
            ("Send updated proposal", "high", -2, "rep"),
            ("Prepare quarterly pipeline review", "medium", 0, "manager"),
            ("Call to confirm kickoff date", "high", 0, "rep"),
            ("Share case study with prospect", "low", 3, "rep2"),
            ("Update contract terms", "medium", 5, "rep"),
            ("Book on-site demo", "medium", 7, "rep2"),
            ("Review overdue invoices with finance", "low", -4, "manager"),
            ("Draft onboarding checklist", "medium", 10, "rep2"),
        ]
        for i, (title, priority, offset, who) in enumerate(specs):
            Task.objects.create(
                title=title,
                priority=priority,
                due_date=today + timedelta(days=offset),
                assignee=users[who],
                created_by=users["manager"],
                contact=contacts[i % len(contacts)],
                description="Fictional demo task.",
            )
        done = Task.objects.filter(auto_created=True).order_by("id")[:2]
        for t in done:
            t.status, t.completed_at = Task.Status.DONE, timezone.now() - timedelta(days=1)
            t.save(update_fields=["status", "completed_at"])

    def _notifications(self, users):
        rules.flag_overdue_leads()
        # make the first few notifications read so the bell shows a realistic mix
        for n in Notification.objects.order_by("created_at")[:3]:
            n.read_at = timezone.now()
            n.save(update_fields=["read_at"])
