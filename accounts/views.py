from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import UserRegisterSerializer, UserLoginSerializer
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class UserViewSet(viewsets.ViewSet):

    def create(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            user.refresh_token = str(refresh)
            user.save()
            return Response({
                'message': 'User registered successfully',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
                if user.check_password(serializer.validated_data['password']):
                    refresh = RefreshToken.for_user(user)
                    return Response({
                        'message': 'User login successfully',
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                        'user_id': user.id,
                    })
                return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
            except User.DoesNotExist:
                return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @action(detail=False, methods=['post'])
    def logout(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Successfully logged out.'}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': 'An error occurred during logout.'}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['post'])
    def refresh(self, request):
        
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            user_id = token['user_id']

            user = User.objects.get(id=user_id)
            
            new_access_token = str(token.access_token)
            
            rotate_refresh_tokens = getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS', False)
        
            if rotate_refresh_tokens:
                new_refresh_token = str(RefreshToken.for_user(token.user))
                return Response({
                    'message': 'Token refreshed successfully',
                    'access': new_access_token,
                    'refresh': new_refresh_token
                })
            
            return Response({
            'message': 'Token refreshed successfully',
            'access': new_access_token
            })

        except TokenError as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.error("User associated with the token does not exist.")
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {str(e)}")
            return Response({'detail': 'An error occurred during token refresh.'}, status=status.HTTP_400_BAD_REQUEST)