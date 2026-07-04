from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, login_not_required
from functools import wraps


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
            messages.error(request, 'You do not have permission to access that page.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_not_required
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                error = 'Your account has been disabled. Contact your administrator.'
        else:
            error = 'Invalid username or password.'
    return render(request, 'accounts/login.html', {'error': error})


@login_not_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_info':
            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            request.user.save()
            messages.success(request, 'Profile updated successfully.')
        elif action == 'change_password':
            old_pw = request.POST.get('old_password', '')
            new_pw1 = request.POST.get('new_password1', '')
            new_pw2 = request.POST.get('new_password2', '')
            if not request.user.check_password(old_pw):
                messages.error(request, 'Current password is incorrect.')
            elif new_pw1 != new_pw2:
                messages.error(request, 'New passwords do not match.')
            elif len(new_pw1) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            else:
                request.user.set_password(new_pw1)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {
        'page_title': 'My Profile',
    })


@admin_required
def user_list(request):
    users = User.objects.select_related().prefetch_related('groups').order_by('username')
    groups = Group.objects.all()
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'groups': groups,
        'page_title': 'User Management',
    })


@admin_required
def user_create(request):
    groups = Group.objects.all()
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '')
        is_active = request.POST.get('is_active') == 'on'
        group_ids = request.POST.getlist('groups')

        if not username:
            messages.error(request, 'Username is required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            user = User.objects.create_user(
                username=username, email=email,
                first_name=first_name, last_name=last_name,
                password=password, is_active=is_active,
            )
            if group_ids:
                user.groups.set(Group.objects.filter(pk__in=group_ids))
            messages.success(request, f'User "{username}" created successfully.')
            return redirect('user_list')

    return render(request, 'accounts/user_form.html', {
        'action': 'Create',
        'groups': groups,
        'page_title': 'Create User',
    })


@admin_required
def user_edit(request, pk):
    edit_user = get_object_or_404(User, pk=pk)
    groups = Group.objects.all()
    if request.method == 'POST':
        edit_user.email = request.POST.get('email', '').strip()
        edit_user.first_name = request.POST.get('first_name', '').strip()
        edit_user.last_name = request.POST.get('last_name', '').strip()
        edit_user.is_active = request.POST.get('is_active') == 'on'
        group_ids = request.POST.getlist('groups')
        new_pw = request.POST.get('new_password', '').strip()
        if new_pw:
            if len(new_pw) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
                return render(request, 'accounts/user_form.html', {
                    'action': 'Edit', 'edit_user': edit_user, 'groups': groups, 'page_title': 'Edit User',
                })
            edit_user.set_password(new_pw)
        edit_user.save()
        edit_user.groups.set(Group.objects.filter(pk__in=group_ids))
        messages.success(request, f'User "{edit_user.username}" updated.')
        return redirect('user_list')

    return render(request, 'accounts/user_form.html', {
        'action': 'Edit',
        'edit_user': edit_user,
        'groups': groups,
        'page_title': f'Edit {edit_user.username}',
    })


@admin_required
@require_POST
def user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
    else:
        user.is_active = not user.is_active
        user.save()
        status = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'User "{user.username}" {status}.')
    return redirect('user_list')
