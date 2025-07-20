from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Listing, Booking, Review

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer with minimal information."""
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email')
        read_only_fields = ('id', 'email')

class UserPublicSerializer(serializers.ModelSerializer):
    """Public user profile serializer."""
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'date_joined')
        read_only_fields = fields

class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for the Review model."""
    user = UserPublicSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'rating', 'title', 'comment', 'stay_date',
            'owner_response', 'response_date', 'created_at', 'updated_at',
            'is_public', 'can_edit'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'response_date')
    
    def get_can_edit(self, obj):
        """Check if the current user can edit this review."""
        request = self.context.get('request')
        return request and request.user == obj.user
    
    def validate_rating(self, value):
        """Validate that rating is between 1 and 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def validate_stay_date(self, value):
        """Validate that stay date is not in the future."""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Stay date cannot be in the future")
        return value

class ReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews with additional validation."""
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment', 'stay_date', 'is_public']
    
    def validate(self, data):
        """
        Validate that the user has a completed booking for this listing.
        """
        listing = self.context['listing']
        user = self.context['request'].user
        
        # Check if user has already reviewed this listing
        if Review.objects.filter(listing=listing, user=user).exists():
            raise serializers.ValidationError("You have already reviewed this listing.")
        
        # Check if user has a completed booking for this listing
        has_completed_booking = Booking.objects.filter(
            listing=listing,
            guest=user,
            status='COMPLETED',
            check_out__lte=timezone.now().date()
        ).exists()
        
        if not has_completed_booking:
            raise serializers.ValidationError(
                "You can only review listings you've stayed at after your stay is completed."
            )
        
        return data

class ListingBasicSerializer(serializers.ModelSerializer):
    """Basic listing serializer with essential fields."""
    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'city', 'country', 'price_per_night',
            'bedrooms', 'bathrooms', 'max_guests', 'property_type',
            'average_rating', 'review_count', 'thumbnail'
        ]
        read_only_fields = fields

class ListingSerializer(serializers.ModelSerializer):
    """Serializer for the Listing model."""
    owner = UserPublicSerializer(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    average_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        read_only=True
    )
    review_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'description', 'address', 'city', 'country',
            'price_per_night', 'bedrooms', 'bathrooms', 'max_guests',
            'property_type', 'amenities', 'is_available', 'owner',
            'average_rating', 'review_count', 'thumbnail',
            'has_wifi', 'has_parking', 'has_kitchen', 'has_air_conditioning',
            'has_heating', 'has_tv', 'has_washer', 'has_pool', 'pet_friendly',
            'latitude', 'longitude', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'owner')
    
    def validate_price_per_night(self, value):
        """Validate that price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price per night must be greater than 0")
        return value

class ListingDetailSerializer(ListingSerializer):
    """Detailed listing serializer with related data."""
    reviews = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    
    class Meta(ListingSerializer.Meta):
        fields = ListingSerializer.Meta.fields + ['reviews', 'is_favorite']
    
    def get_reviews(self, obj):
        """Get paginated reviews for the listing."""
        from rest_framework.pagination import PageNumberPagination
        from rest_framework.request import Request
        
        reviews = obj.reviews.filter(is_public=True).order_by('-created_at')
        
        # Check if we're in a request context with pagination
        if isinstance(self.context.get('request'), Request):
            paginator = PageNumberPagination()
            paginated_reviews = paginator.paginate_queryset(reviews, self.context['request'])
            serializer = ReviewSerializer(paginated_reviews, many=True, context=self.context)
            return paginator.get_paginated_response(serializer.data).data
        
        # Return all reviews if not in a request context
        return ReviewSerializer(reviews, many=True, context=self.context).data
    
    def get_is_favorite(self, obj):
        """Check if the current user has favorited this listing."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorited_by.filter(pk=request.user.pk).exists()
        return False

class BookingSerializer(serializers.ModelSerializer):
    """Serializer for the Booking model."""
    guest = UserPublicSerializer(read_only=True)
    listing = ListingBasicSerializer(read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.all(),
        source='listing',
        write_only=True
    )
    status = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = Booking
        fields = [
            'id', 'listing', 'listing_id', 'guest', 'check_in', 'check_out',
            'guests', 'total_price', 'status', 'special_requests',
            'cancelled_at', 'cancellation_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = (
            'id', 'guest', 'status', 'total_price', 'cancelled_at',
            'cancellation_reason', 'created_at', 'updated_at'
        )
    
    def validate(self, data):
        """
        Validate booking data including date ranges and availability.
        """
        check_in = data.get('check_in')
        check_out = data.get('check_out')
        listing = data.get('listing')
        guests = data.get('guests', 1)
        
        # Check date validity
        if check_in and check_out:
            # Check date range
            if check_in < timezone.now().date():
                raise serializers.ValidationError({
                    'check_in': 'Check-in date cannot be in the past.'
                })
                
            if check_out <= check_in:
                raise serializers.ValidationError({
                    'check_out': 'Check-out date must be after check-in date.'
                })
            
            # Check minimum stay (example: 1 night)
            if (check_out - check_in).days < 1:
                raise serializers.ValidationError({
                    'check_out': 'Minimum stay is 1 night.'
                })
            
            # Check maximum stay (example: 30 days)
            if (check_out - check_in).days > 30:
                raise serializers.ValidationError({
                    'check_out': 'Maximum stay is 30 nights.'
                })
            
            # Check listing availability
            if listing and not listing.is_available:
                raise serializers.ValidationError({
                    'listing': 'This listing is not available for booking.'
                })
            
            # Check for overlapping bookings
            overlapping_bookings = Booking.objects.filter(
                listing=listing,
                check_out__gt=check_in,
                check_in__lt=check_out,
                status__in=['PENDING', 'CONFIRMED']
            )
            
            if self.instance:
                overlapping_bookings = overlapping_bookings.exclude(pk=self.instance.pk)
                
            if overlapping_bookings.exists():
                raise serializers.ValidationError({
                    'check_in': 'This listing is not available for the selected dates.'
                })
        
        # Validate number of guests
        if listing and guests > listing.max_guests:
            raise serializers.ValidationError({
                'guests': f'Maximum {listing.max_guests} guests allowed for this listing.'
            })
        
        return data
    
    def create(self, validated_data):
        """Create a new booking with calculated total price."""
        listing = validated_data['listing']
        check_in = validated_data['check_in']
        check_out = validated_data['check_out']
        
        # Calculate total price
        nights = (check_out - check_in).days
        total_price = listing.price_per_night * nights
        
        # Add additional charges if needed (e.g., cleaning fee, taxes)
        # total_price += Decimal('50.00')  # Example: Add cleaning fee
        
        # Create the booking
        booking = Booking.objects.create(
            **validated_data,
            guest=self.context['request'].user,
            total_price=total_price,
            status='PENDING'  # Or 'CONFIRMED' based on your business logic
        )
        
        return booking

class BookingDetailSerializer(BookingSerializer):
    """Detailed booking serializer with nested listing and review status."""
    can_review = serializers.SerializerMethodField()
    has_reviewed = serializers.SerializerMethodField()
    
    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ['can_review', 'has_reviewed']
    
    def get_can_review(self, obj):
        """Check if the booking can be reviewed."""
        if not obj.status == 'COMPLETED':
            return False
            
        if not hasattr(obj, 'has_reviewed'):
            obj.has_reviewed = obj.reviews.exists()
            
        return not obj.has_reviewed
    
    def get_has_reviewed(self, obj):
        """Check if the booking has been reviewed."""
        if not hasattr(obj, 'has_reviewed'):
            obj.has_reviewed = obj.reviews.exists()
        return obj.has_reviewed
