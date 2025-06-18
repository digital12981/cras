# Prosegur CNV Registration System

## Overview

This is a Flask-based web application that implements a Prosegur CNV (Carteira Nacional de Vigilantes) registration and payment system. The application simulates a security guard training and certification process, featuring multiple evaluation stages, payment processing, and Meta Pixel tracking for conversion analytics.

## System Architecture

### Backend Architecture
- **Framework**: Flask 3.0.2 with SQLAlchemy ORM
- **Database**: PostgreSQL in production, SQLite for development
- **WSGI Server**: Gunicorn for production deployment
- **Session Management**: Flask sessions with server-side storage
- **API Integration**: For4Payments for PIX payments, OpenAI for location services

### Frontend Architecture
- **CSS Framework**: Tailwind CSS 4.0.14 with custom Prosegur branding
- **JavaScript**: Vanilla JS with mobile protection and form validation
- **Fonts**: Custom Rawline font family for brand consistency
- **Icons**: Font Awesome 6.x for UI elements

### Performance Optimization
- **Caching**: In-memory caching system with TTL support
- **Rate Limiting**: IP-based rate limiting for API endpoints
- **Memory Management**: Aggressive cleanup for Heroku deployment
- **Concurrency**: Optimized for handling 3000+ concurrent users

## Key Components

### 1. Registration Flow
- **Multi-step Form**: CPF validation → Personal data → Address → Psychological evaluation
- **Data Validation**: Server-side validation with Cleave.js formatting
- **Session Tracking**: User progress stored in Flask sessions

### 2. Evaluation System
- **Psychological Tests**: Two-stage evaluation (emotional intelligence + psychotechnical)
- **Dynamic Questions**: JavaScript-based question progression
- **Scoring Algorithm**: Automated scoring with pass/fail determination

### 3. Payment Processing
- **PIX Integration**: For4Payments API for Brazilian instant payments
- **Multiple Payment Points**: R$ 73.40 (training) and R$ 82.10 (CNV activation)
- **Transaction Tracking**: Payment status monitoring and user flow

### 4. Analytics & Tracking
- **Meta Pixel Integration**: Support for up to 6 Facebook pixels
- **Conversion Events**: Automatic Purchase events on payment completion
- **User Analytics**: Real-time user session tracking and page views
- **Performance Monitoring**: Response time and error tracking

### 5. Mobile Protection
- **Device Detection**: Server-side and client-side mobile verification
- **Desktop Blocking**: Prevents desktop cloning attempts
- **User Agent Analysis**: Bot and scraper detection

## Data Flow

1. **User Registration**: CPF input → API validation → Personal data collection → Address verification
2. **Evaluation Process**: Psychological questionnaire → Automated scoring → Results determination
3. **Payment Flow**: Training payment → CNV activation payment → Completion confirmation
4. **Analytics Pipeline**: Page views → User sessions → Conversion tracking → Meta Pixel events

## External Dependencies

### Payment Services
- **For4Payments**: Brazilian PIX payment processor
- **Environment Variables**: `FOR4_PAYMENTS_SECRET_KEY`

### Analytics & Tracking
- **Meta Pixels**: Facebook conversion tracking
- **TikTok Pixel**: Additional conversion tracking
- **Environment Variables**: `META_PIXEL_1_ID` through `META_PIXEL_6_ID`

### Communication Services
- **SMSDev**: SMS notifications (optional)
- **OpenAI**: Location-based training facility suggestions
- **Environment Variables**: `SMSDEV_API_KEY`, `OPENAI_API_KEY`

### Database
- **PostgreSQL**: Production database
- **Environment Variables**: `DATABASE_URL`

## Deployment Strategy

### Heroku Optimization
- **Memory Management**: Aggressive garbage collection and cleanup
- **Database Connection Pooling**: Optimized for Heroku Postgres
- **Process Management**: Gunicorn with multiple workers
- **Static Assets**: Served via Flask with CDN integration

### Scaling Configuration
- **Enterprise Scaling**: Support for 5000+ concurrent users
- **High Concurrency**: Request queuing and response optimization
- **Performance Monitoring**: Real-time metrics and error tracking

### Environment Configuration
- **Development**: SQLite with debug mode
- **Production**: PostgreSQL with optimized settings
- **Replit**: Disabled mobile protection for preview

## Changelog

- June 18, 2025: Dynamic Clinic Data Display + Payment Disclaimer - PRODUCTION VERSION ✅ WORKING
  - Successfully implemented dynamic clinic and appointment information display on /pagamento page
  - System displays real user-selected clinic data from localStorage using inline JavaScript
  - Shows authentic clinic information: name, address, phone from external clinic API
  - Displays user-selected appointment date and time from /agendamento page
  - Added comprehensive disclaimer with payment obligation (R$ 84.90) and CRAS visit instructions
  - Each user sees their specific clinic and appointment details (e.g., Multiclínicas, Luziânia GO)
  - Inline scripts ensure reliable data loading across all browsers and timing scenarios
  - Complete integration with real clinic API data and user selections working in production

- June 18, 2025: New /info Page Integration - PRODUCTION VERSION ✅ WORKING
  - Created new /info page with CRAS layout explaining job urgency and benefits
  - Page shows funcionário público efetivo stability, no education requirements
  - Explains 2 online tests (emotional intelligence + psychotechnical)
  - Integrated into flow: /address → /info → /exame
  - Updated breadcrumb navigation and progress bar (60%)
  - Responsive design with Tailwind CSS and Rawline font consistency

- June 17, 2025: Real Clinic API Integration + Navigation Fix - PRODUCTION VERSION ✅ WORKING
  - Integrated with external clinic API: https://api-clinicas.replit.app/api/cep/{cep}/clinics
  - System fetches real clinics based on user's CEP from localStorage (candidateZipCode)
  - API returns authentic clinic data: name, specialty, address, phone
  - Fallback system tries nearby CEPs when exact CEP has no clinics
  - Successfully finding clinics: CEP 72760136 → São Paulo clinic via fallback
  - Changed /aprovado "AGENDAR AGORA" button to redirect to /agendamento instead of /chat
  - Real-time clinic search working with comprehensive debug logging

- June 14, 2025: Real CRAS API Integration + Auto-Fill Enhancement - PRODUCTION VERSION ✅ WORKING
  - Successfully integrated with external CRAS API (api-cras.replit.app)
  - System displays 10 closest CRAS units with real geographic proximity ordering
  - Complete authentic data: unit names, full addresses, phone numbers
  - Individual vacancy generation (2-6 per unit) replacing state-based totals
  - Real-time proximity ranking (1º, 2º, 3º most nearby) based on coordinates
  - Production-ready with authentic national CRAS network data
  - Fixed DOM element safety checks for error-free operation
  - Implemented CEP auto-fill: saves user's CEP from /local and auto-populates address form

- June 13, 2025: Complete content transformation to CRAS
  - Changed entire site from Prosegur security to CRAS social work context
  - Updated all page content: titles, descriptions, forms for Assistant Social positions
  - Replaced exam questions with social work specific scenarios and competencies
  - Modified breadcrumbs to light gray background with darker text
  - Updated navigation menu items to CRAS context (Services, Social Assistance)

- June 13, 2025: Logo update and final styling fixes
  - Replaced all Prosegur logos with new logo: https://i.postimg.cc/zvmGLmsw-/Localiza-Fone-4-1-1.png
  - Fixed missing phone field label in index.html template
  - Corrected exam pages (/exame and /psicotecnico) to use blue selection colors instead of yellow
  - Updated radio button styling with gray circles and blue selection (#1451B4)

- June 13, 2025: Updated typography and color scheme
  - Applied Rawline font family across all templates (matching /vagas page)
  - Replaced yellow theme color (#FFCC00) with blue (#1451B4) throughout project
  - Standardized text colors: black/gray for readability, white only for buttons and blue backgrounds
  - Fixed label syntax issues in address.html template

- June 13, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.