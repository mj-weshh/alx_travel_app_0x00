import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from faker import Faker

# Import your models here
from listings.models import Listing, Booking, Review

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with sample data for listings, bookings, and reviews'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of users to create (default: 5)',
        )
        parser.add_argument(
            '--listings',
            type=int,
            default=10,
            help='Number of listings to create (default: 10)',
        )
        parser.add_argument(
            '--bookings',
            type=int,
            default=20,
            help='Number of bookings to create (default: 20)',
        )
        parser.add_argument(
            '--reviews',
            type=int,
            default=15,
            help='Number of reviews to create (default: 15)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database seeding...'))
        
        # Clear existing data if --clear flag is set
        if options['clear']:
            self.clear_data()
        
        # Create sample data
        self.faker = Faker()
        
        # Create users
        users = self.create_users(options['users'])
        
        # Create listings
        listings = self.create_listings(options['listings'], users)
        
        # Create bookings
        bookings = self.create_bookings(options['bookings'], users, listings)
        
        # Create reviews
        self.create_reviews(options['reviews'], users, bookings)
        
        self.stdout.write(
            self.style.SUCCESS('Successfully seeded the database with sample data')
        )
    
    def clear_data(self):
        """Clear existing data from the database."""
        self.stdout.write('Clearing existing data...')
        
        # Clear data in reverse order of foreign key dependencies
        Review.objects.all().delete()
        Booking.objects.all().delete()
        Listing.objects.all().delete()
        
        # Don't delete superusers
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS('Successfully cleared existing data'))
    
    def create_users(self, count):
        """Create sample users."""
        self.stdout.write(f'Creating {count} sample users...')
        
        users = []
        for i in range(count):
            username = f'user{i+1}'
            email = f'{username}@example.com'
            
            # Skip if user already exists
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                users.append(user)
                continue
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password='password123',
                first_name=self.faker.first_name(),
                last_name=self.faker.last_name(),
            )
            users.append(user)
            
            # Create a superuser if this is the first user
            if i == 0 and not User.objects.filter(is_superuser=True).exists():
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Created superuser: {user.username}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(users)} users'))
        return users
    
    def create_listings(self, count, owners):
        """Create sample listings."""
        self.stdout.write(f'Creating {count} sample listings...')
        
        property_types = [choice[0] for choice in Listing.PROPERTY_TYPES]
        cities = [
            ('New York', 'US'), ('Los Angeles', 'US'), ('Chicago', 'US'),
            ('London', 'UK'), ('Paris', 'France'), ('Tokyo', 'Japan'),
            ('Sydney', 'Australia'), ('Barcelona', 'Spain'), ('Rome', 'Italy'),
            ('Amsterdam', 'Netherlands')
        ]
        
        amenities_list = [
            'WiFi', 'Kitchen', 'Washer', 'Dryer', 'Air conditioning',
            'Heating', 'TV', 'Hair dryer', 'Iron', 'Laptop-friendly workspace',
            'Pool', 'Hot tub', 'Free parking', 'Gym', 'Breakfast',
            'Pets allowed', 'Smoking allowed', 'Wheelchair accessible'
        ]
        
        listings = []
        for i in range(count):
            city, country = random.choice(cities)
            owner = random.choice(owners)
            
            # Generate random coordinates within the city's general area
            latitude = random.uniform(-90, 90)
            longitude = random.uniform(-180, 180)
            
            # Generate random amenities (3-8 random amenities per listing)
            amenities = random.sample(
                amenities_list,
                k=random.randint(3, min(8, len(amenities_list)))
            )
            
            # Determine property features based on amenities
            has_wifi = 'WiFi' in amenities
            has_parking = 'Free parking' in amenities
            has_kitchen = 'Kitchen' in amenities
            has_air_conditioning = 'Air conditioning' in amenities
            has_heating = 'Heating' in amenities
            has_tv = 'TV' in amenities
            has_washer = 'Washer' in amenities
            has_pool = 'Pool' in amenities
            pet_friendly = 'Pets allowed' in amenities
            
            listing = Listing.objects.create(
                title=f"{self.faker.word().title()} {random.choice(['House', 'Apartment', 'Villa', 'Cabin', 'Loft'])} in {city}",
                description=self.faker.paragraph(nb_sentences=5),
                address=f"{random.randint(1, 999)} {self.faker.street_name()}",
                city=city,
                country=country,
                price_per_night=round(random.uniform(50, 500), 2),
                bedrooms=random.randint(1, 5),
                bathrooms=round(random.uniform(1, 4.5) * 2) / 2,  # 1, 1.5, 2, 2.5, etc.
                max_guests=random.randint(1, 10),
                property_type=random.choice(property_types),
                amenities=amenities,
                owner=owner,
                has_wifi=has_wifi,
                has_parking=has_parking,
                has_kitchen=has_kitchen,
                has_air_conditioning=has_air_conditioning,
                has_heating=has_heating,
                has_tv=has_tv,
                has_washer=has_washer,
                has_pool=has_pool,
                pet_friendly=pet_friendly,
                latitude=latitude,
                longitude=longitude,
            )
            
            listings.append(listing)
            
            # Add a thumbnail image (placeholder)
            # In a real app, you would save actual image files here
            # listing.thumbnail.save(f'listing_{listing.id}.jpg', ContentFile(b''), save=True)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(listings)} listings'))
        return listings
    
    def create_bookings(self, count, users, listings):
        """Create sample bookings."""
        self.stdout.write(f'Creating {count} sample bookings...')
        
        if not listings or not users:
            self.stdout.write(self.style.WARNING('No listings or users available to create bookings'))
            return []
        
        bookings = []
        status_choices = ['PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED']
        
        for _ in range(count):
            listing = random.choice(listings)
            guest = random.choice(users)
            
            # Generate random check-in date (between 60 days ago and 60 days in the future)
            check_in = timezone.now().date() + timedelta(days=random.randint(-60, 60))
            
            # Generate check-out date (1-14 days after check-in)
            check_out = check_in + timedelta(days=random.randint(1, 14))
            
            # Skip if check-in is in the past and status is PENDING
            status = random.choices(
                status_choices,
                weights=[0.2, 0.5, 0.2, 0.1],  # Higher probability for CONFIRMED
                k=1
            )[0]
            
            if check_in < timezone.now().date() and status == 'PENDING':
                status = 'CANCELLED'  # Auto-cancel past pending bookings
            
            # Generate random number of guests (1 to max_guests for the listing)
            guests = random.randint(1, listing.max_guests)
            
            # Calculate total price
            nights = (check_out - check_in).days
            total_price = listing.price_per_night * nights
            
            # Add some random special requests (30% chance)
            special_requests = None
            if random.random() < 0.3:
                special_requests = self.faker.sentence()
            
            # Create the booking
            booking = Booking.objects.create(
                listing=listing,
                guest=guest,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                total_price=total_price,
                status=status,
                special_requests=special_requests,
            )
            
            # If status is CANCELLED, set cancelled_at to a random time between creation and now
            if status == 'CANCELLED':
                booking.cancelled_at = timezone.now() - timedelta(days=random.randint(1, 30))
                booking.cancellation_reason = random.choice([
                    'Change of plans', 'Found a better deal', 'Unexpected circumstances',
                    'Travel restrictions', 'Personal reasons'
                ])
                booking.save()
            
            bookings.append(booking)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(bookings)} bookings'))
        return bookings
    
    def create_reviews(self, count, users, bookings):
        """Create sample reviews."""
        self.stdout.write(f'Creating {count} sample reviews...')
        
        if not bookings:
            self.stdout.write(self.style.WARNING('No bookings available to create reviews'))
            return []
        
        # Only use COMPLETED bookings for reviews
        completed_bookings = [b for b in bookings if b.status == 'COMPLETED']
        
        if not completed_bookings:
            self.stdout.write(self.style.WARNING('No completed bookings available to create reviews'))
            return []
        
        reviews = []
        
        # Ensure we don't create more reviews than available bookings
        count = min(count, len(completed_bookings))
        
        # Randomly select bookings to review (without replacement)
        selected_bookings = random.sample(completed_bookings, count)
        
        for booking in selected_bookings:
            # Skip if this booking already has a review
            if hasattr(booking, 'review'):
                continue
            
            # Generate a random rating (1-5)
            rating = random.choices(
                [1, 2, 3, 4, 5],
                weights=[0.05, 0.1, 0.2, 0.3, 0.35],  # Higher probability for 4-5 star ratings
                k=1
            )[0]
            
            # Generate review content based on rating
            if rating == 5:
                title = random.choice([
                    'Amazing stay!', 'Perfect in every way', 'Highly recommended',
                    'Will definitely come back', 'Absolutely wonderful'
                ])
                comment = self.faker.paragraph(nb_sentences=3)
            elif rating == 4:
                title = random.choice([
                    'Great place', 'Very nice stay', 'Enjoyed our time here',
                    'Comfortable and clean', 'Good experience overall'
                ])
                comment = self.faker.paragraph(nb_sentences=2)
            elif rating == 3:
                title = random.choice([
                    'Decent place', 'Average experience', 'It was okay',
                    'Met expectations', 'Nothing special'
                ])
                comment = self.faker.paragraph(nb_sentences=2)
            elif rating == 2:
                title = random.choice([
                    'Disappointing', 'Could be better', 'Not what I expected',
                    'Several issues', 'Below average'
                ])
                comment = self.faker.paragraph(nb_sentences=2)
            else:  # rating == 1
                title = random.choice([
                    'Terrible experience', 'Would not recommend', 'Very disappointing',
                    'Worst stay ever', 'Never again'
                ])
                comment = self.faker.paragraph(nb_sentences=3)
            
            # Generate a random stay date (between check-in and check-out)
            stay_date = booking.check_in + timedelta(
                days=random.randint(0, (booking.check_out - booking.check_in).days - 1)
            )
            
            # Create the review
            review = Review.objects.create(
                listing=booking.listing,
                user=booking.guest,
                rating=rating,
                title=title,
                comment=comment,
                stay_date=stay_date,
                is_public=random.choices([True, False], weights=[0.9, 0.1], k=1)[0],
            )
            
            # 20% chance of owner response
            if random.random() < 0.2:
                review.owner_response = random.choice([
                    'Thank you for your feedback!',
                    'We appreciate your review and hope to host you again!',
                    'Thanks for staying with us!',
                    'We\'re glad you enjoyed your stay!',
                    'We appreciate your honest feedback.'
                ])
                review.response_date = review.created_at + timedelta(days=random.randint(1, 7))
                review.save()
            
            reviews.append(review)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(reviews)} reviews'))
        return reviews
