from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

User = get_user_model()

def validate_future_date(value):
    if value < timezone.now().date():
        raise ValidationError("Date cannot be in the past")

def validate_check_out_after_check_in(booking):
    if booking.check_out <= booking.check_in:
        raise ValidationError("Check-out date must be after check-in date")

class Listing(models.Model):
    PROPERTY_TYPES = [
        ('HOUSE', 'House'),
        ('APARTMENT', 'Apartment'),
        ('HOTEL', 'Hotel'),
        ('VILLA', 'Villa'),
        ('CABIN', 'Cabin'),
        ('RESORT', 'Resort'),
        ('BEACH_HOUSE', 'Beach House'),
        ('TREEHOUSE', 'Treehouse'),
    ]

    title = models.CharField(max_length=200, help_text="The title of the property listing")
    description = models.TextField(help_text="Detailed description of the property")
    address = models.CharField(max_length=255, help_text="Full street address")
    city = models.CharField(max_length=100, help_text="City where the property is located")
    country = models.CharField(max_length=100, help_text="Country where the property is located")
    price_per_night = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Price per night in local currency"
    )
    bedrooms = models.PositiveIntegerField(help_text="Number of bedrooms")
    bathrooms = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.5)],
        help_text="Number of bathrooms (can be half bathrooms)"
    )
    max_guests = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Maximum number of guests allowed"
    )
    property_type = models.CharField(
        max_length=20, 
        choices=PROPERTY_TYPES,
        help_text="Type of the property"
    )
    amenities = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of amenities available (e.g., ['WiFi', 'Pool', 'Kitchen'])"
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether the property is available for booking"
    )
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='owned_listings',
        help_text="User who owns this listing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional fields for better search and filtering
    has_wifi = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    has_air_conditioning = models.BooleanField(default=False)
    has_heating = models.BooleanField(default=False)
    has_tv = models.BooleanField(default=False)
    has_washer = models.BooleanField(default=False)
    has_pool = models.BooleanField(default=False)
    pet_friendly = models.BooleanField(default=False)
    
    # Location details
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Geographic latitude"
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Geographic longitude"
    )

    def __str__(self):
        return f"{self.title} - {self.city}, {self.country}"

    class Meta:
        ordering = ['-created_at']

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
        ('NO_SHOW', 'No Show'),
    ]

    listing = models.ForeignKey(
        Listing, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="The property being booked"
    )
    guest = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        help_text="User who made the booking"
    )
    check_in = models.DateField(
        validators=[validate_future_date],
        help_text="Check-in date"
    )
    check_out = models.DateField(
        validators=[validate_future_date],
        help_text="Check-out date"
    )
    guests = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of guests"
    )
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Total price for the booking"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Current status of the booking"
    )
    special_requests = models.TextField(
        blank=True,
        null=True,
        help_text="Any special requests from the guest"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.guest.email} - {self.listing.title} ({self.check_in} to {self.check_out})"

    def clean(self):
        super().clean()
        if self.check_in and self.check_out:
            if self.check_out <= self.check_in:
                raise ValidationError("Check-out date must be after check-in date")
            
            # Check for overlapping bookings
            overlapping = Booking.objects.filter(
                listing=self.listing,
                check_out__gt=self.check_in,
                check_in__lt=self.check_out,
                status__in=['PENDING', 'CONFIRMED']
            ).exclude(pk=self.pk if self.pk else None)
            
            if overlapping.exists():
                raise ValidationError("This property is already booked for the selected dates.")
            
            # Validate number of guests doesn't exceed listing capacity
            if self.guests > self.listing.max_guests:
                raise ValidationError(
                    f"Number of guests ({self.guests}) exceeds the maximum allowed ({self.listing.max_guests})"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        # Calculate total price if not set
        if not self.total_price and self.check_in and self.check_out and self.listing:
            nights = (self.check_out - self.check_in).days
            self.total_price = self.listing.price_per_night * nights
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(check_out__gt=models.F('check_in')),
                name='check_out_after_check_in',
                violation_error_message="Check-out date must be after check-in date"
            ),
            models.CheckConstraint(
                check=models.Q(guests__gt=0),
                name='at_least_one_guest',
                violation_error_message="Number of guests must be at least 1"
            )
        ]
        
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['check_in', 'check_out']),
            models.Index(fields=['guest']),
            models.Index(fields=['listing', 'status']),
        ]


class Review(models.Model):
    """
    Model representing user reviews for listings.
    """
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="The listing being reviewed"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="User who wrote the review"
    )
    
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (poor) to 5 (excellent)"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="A short title for the review"
    )
    
    comment = models.TextField(
        help_text="Detailed review comments"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional metadata
    stay_date = models.DateField(
        null=True,
        blank=True,
        help_text="When the user stayed at the property"
    )
    
    is_public = models.BooleanField(
        default=True,
        help_text="Whether the review is visible to others"
    )
    
    # Response from the host
    owner_response = models.TextField(
        blank=True,
        null=True,
        help_text="Response from the property owner"
    )
    
    response_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the owner responded to the review"
    )
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['listing', 'user']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        indexes = [
            models.Index(fields=['listing', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['rating']),
            models.Index(fields=['is_public']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s review of {self.listing.title} - {self.rating}/5"
    
    def clean(self):
        super().clean()
        
        # Ensure the user has actually booked the property to leave a review
        if not Booking.objects.filter(
            listing=self.listing,
            guest=self.user,
            status='COMPLETED',
            check_out__lte=timezone.now().date()
        ).exists():
            raise ValidationError("You can only review properties you've actually stayed at.")
        
        # Validate stay date is not in the future
        if self.stay_date and self.stay_date > timezone.now().date():
            raise ValidationError("Stay date cannot be in the future.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update the listing's average rating
        self.listing.update_average_rating()
    
    def delete(self, *args, **kwargs):
        listing = self.listing
        super().delete(*args, **kwargs)
        # Update the listing's average rating after deletion
        listing.update_average_rating()

# Add the update_average_rating method to the Listing model
def update_average_rating(self):
    """
    Update the average rating for the listing based on all its reviews.
    """
    from django.db.models import Avg, Count
    
    result = Review.objects.filter(
        listing=self,
        is_public=True
    ).aggregate(
        average_rating=Avg('rating'),
        review_count=Count('id')
    )
    
    self.average_rating = result['average_rating'] or 0
    self.review_count = result['review_count']
    
    # Save without triggering signals to avoid infinite loops
    Listing.objects.filter(pk=self.pk).update(
        average_rating=self.average_rating,
        review_count=self.review_count
    )

# Add the method to the Listing model
Listing.update_average_rating = update_average_rating

# Add the average_rating and review_count fields to the Listing model
Listing.add_to_class('average_rating', models.DecimalField(
    max_digits=3,
    decimal_places=2,
    default=0.00,
    editable=False,
    help_text="Average rating from all reviews (1-5)"
))

Listing.add_to_class('review_count', models.PositiveIntegerField(
    default=0,
    editable=False,
    help_text="Total number of reviews for this listing"
))
