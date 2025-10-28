# 🎨 UI/UX Designer & WinUI 3 Expert Recruitment
## DirectAI Music Platform - Windows Desktop Experience

---

## 📋 Position Overview

**Project:** DirectAI Studio - AI-Powered Music Creation Platform (WinUI 3)

**Objective:** Transform our functional WinUI 3 desktop application into a **world-class music production interface** that rivals professional DAWs like Ableton Live, FL Studio, and Logic Pro. We need designers and developers who can create an intuitive, beautiful, and performant experience for musicians and producers.

**Current State:**
- ✅ Working WinUI 3 application with basic functionality
- ✅ MVVM architecture with CommunityToolkit.Mvvm
- ✅ Backend integration complete (API, database, workers)
- ⚠️ UI needs significant UX refinement and visual polish
- ⚠️ Drag-and-drop and timeline interactions need optimization
- ⚠️ Color scheme, typography, and spacing need professional design

**Technology Stack:**
- **WinUI 3** (.NET 9.0, C#, XAML)
- **Windows App SDK** (latest)
- **CommunityToolkit.Mvvm** (MVVM pattern)
- **Microsoft.UI.Xaml.Controls** (modern controls)

**Budget:** $60K - $120K (depending on scope and timeline)  
**Timeline:** 8-12 weeks for MVP redesign, ongoing refinement  
**Location:** Remote-first (any timezone)

---

## 🎯 Core Responsibilities

### 1️⃣ UI/UX Design Lead

**Design Vision:**
- Create a **dark, modern, music-production-focused** interface
- Design inspiration: SUNO Studio, Ableton Live, Splice, Soundtrap
- Establish **design system** (colors, typography, spacing, components)
- Design **user flows** for key scenarios:
  - Audio library browsing and management
  - Multitrack timeline editing
  - Drag-and-drop stem arrangement
  - AI music generation workflows
  - Mixing and playback controls

**Deliverables:**
- High-fidelity mockups (Figma, Adobe XD, Sketch)
- Design system documentation (component library)
- Interactive prototypes for key workflows
- User testing sessions and iteration
- Handoff assets for WinUI 3 implementation

**Required Skills:**
- 5+ years UI/UX design experience
- Portfolio with **music/audio/creative software** (DAWs, audio editors, music apps)
- Expertise in **dark UI themes** and color theory
- Strong typography and visual hierarchy skills
- Experience designing for **desktop applications** (not just web/mobile)
- Proficiency with Figma or Adobe XD

**Nice to Have:**
- Background in music production or audio engineering
- Experience with Windows design guidelines (Fluent Design System)
- Understanding of accessibility standards (WCAG)
- Animation and micro-interaction design skills

**Rate:** $90 - $150/hour (USD)

---

### 2️⃣ Senior WinUI 3 Developer

**Technical Implementation:**
- Convert design mockups to **pixel-perfect XAML**
- Implement **custom controls and templates**:
  - Timeline/waveform visualizer
  - Drag-and-drop audio cards
  - Custom sliders, knobs, and meters
  - Audio playback transport controls
- Optimize **performance and responsiveness**:
  - Smooth scrolling and animations
  - Efficient rendering of large audio libraries
  - GPU-accelerated waveform drawing
- Implement **advanced WinUI 3 patterns**:
  - Attached behaviors for drag-and-drop
  - Custom renderers for audio visualization
  - MVVM bindings with converters
  - Resource dictionaries and styling

**Deliverables:**
- Production-ready XAML views and controls
- Reusable control library
- Performance optimization report
- Code documentation and best practices guide
- Unit tests for custom controls

**Required Skills:**
- 4+ years WinUI 3 / UWP / WPF experience
- Expert-level XAML and C# knowledge
- Deep understanding of **WinUI 3 limitations and workarounds**:
  - No `RelativeSource` binding (must use `ElementName`)
  - ScrollViewer drag-drop event routing issues
  - Custom control templating best practices
- Experience with **MVVM pattern** (CommunityToolkit.Mvvm preferred)
- Strong performance optimization skills (profiling, memory management)
- Git version control and pull request workflow

**Nice to Have:**
- Experience building audio/video applications
- Knowledge of Win2D or DirectX for custom rendering
- Background in animation and visual effects
- Contributions to open-source WinUI projects

**Rate:** $100 - $160/hour (USD)

---

### 3️⃣ UX Researcher / Usability Specialist

**User Research:**
- Conduct **user interviews** with music producers
- Perform **usability testing** on current interface
- Create **user personas** and journey maps
- Identify **pain points** and improvement opportunities
- A/B test design iterations

**Deliverables:**
- User research report with key findings
- Usability testing sessions (5-10 participants)
- Recommendations for UX improvements
- User persona documentation
- Journey maps for key workflows

**Required Skills:**
- 3+ years UX research experience
- Experience conducting usability tests
- Familiarity with music production workflows
- Strong analytical and reporting skills
- Ability to translate research into actionable design changes

**Nice to Have:**
- Background in music production or audio engineering
- Experience with creative software user testing
- Knowledge of accessibility testing

**Rate:** $70 - $120/hour (USD)

---

### 4️⃣ Motion Designer / Animator

**Visual Polish:**
- Design **micro-interactions** and animations:
  - Hover states, transitions, loading indicators
  - Playback cursor animation
  - Waveform visualizations
  - Button press feedback
- Create **onboarding animations**
- Design **loading and progress indicators**
- Implement **smooth transitions** between views

**Deliverables:**
- Animation specifications (Lottie, After Effects)
- XAML Storyboard implementations
- Motion design system documentation
- Interactive prototype with animations

**Required Skills:**
- 3+ years motion design experience
- Proficiency with After Effects or similar tools
- Understanding of animation principles (easing, timing, etc.)
- Experience translating animations to code (CSS, XAML, or Unity)

**Nice to Have:**
- Experience with audio-reactive visualizations
- Knowledge of XAML Storyboards and animations
- Background in music video or audio software design

**Rate:** $80 - $130/hour (USD)

---

## 🎨 Design Requirements

### Visual Style Guide
- **Color Palette:**
  - Primary: Purple/Magenta accent (#8B5CF6, #E935C1)
  - Background: Dark grays (#0f0f0f, #1a1a1a, #2a2a2a)
  - Text: White (#FFFFFF) and gray (#999999, #666666)
  - Success/Error: Green/Red for status indicators
- **Typography:**
  - Headers: Segoe UI, Inter, or SF Pro (16-24px, SemiBold)
  - Body: Segoe UI (12-14px, Regular)
  - Monospace: Consolas or JetBrains Mono (time displays)
- **Spacing:**
  - Use 4px grid system (4, 8, 12, 16, 24, 32px)
- **Iconography:**
  - Fluent UI Icons (Segoe MDL2 Assets)
  - Consistent icon sizing (12px, 14px, 16px, 20px, 24px)

### Key Interface Components

#### 1. Audio Library Sidebar
- **Card-based layout** for audio files
- Album art thumbnails
- File metadata (title, duration, format)
- Action buttons (add to mix, play, delete)
- **Drag-and-drop** support

#### 2. Multitrack Timeline
- **Horizontal scrolling timeline** with time ruler
- **Vertical track lanes** with waveform visualizations
- **Playback cursor** with current time display
- **Zoom controls** (horizontal and vertical)
- **Snap-to-grid** for precise editing

#### 3. Transport Controls
- Large play/pause button (center)
- Skip, stop, record buttons
- Time display (current / total duration)
- Volume controls and meters

#### 4. Generation Panel
- Prompt input with AI suggestions
- Parameter controls (BPM, key, duration)
- Style/genre selectors
- Generate button with progress indicator

#### 5. Mixing Console
- Track volume sliders
- Pan controls
- Mute/solo buttons
- Effects chain visualization

---

## 📦 Deliverables & Milestones

### Phase 1: Design Foundation (Weeks 1-3)
- [ ] User research and persona development
- [ ] Design system creation (colors, typography, spacing)
- [ ] Component library design (buttons, cards, sliders)
- [ ] High-fidelity mockups for key screens

### Phase 2: UX Refinement (Weeks 4-6)
- [ ] Interactive prototypes (Figma/Adobe XD)
- [ ] Usability testing sessions (5+ users)
- [ ] Design iteration based on feedback
- [ ] Animation and micro-interaction specifications

### Phase 3: Implementation (Weeks 7-10)
- [ ] XAML implementation of designs
- [ ] Custom control development
- [ ] Animation and transition implementation
- [ ] Performance optimization

### Phase 4: Polish & Launch (Weeks 11-12)
- [ ] Final usability testing
- [ ] Bug fixes and refinements
- [ ] Documentation and design handoff
- [ ] Launch preparation

---

## ✅ Selection Criteria

### Must Have:
✅ **Portfolio with music/audio software** (DAWs, audio editors, creative tools)  
✅ **Experience with dark UI themes** and modern design trends  
✅ **Desktop application experience** (not just web/mobile)  
✅ **Strong attention to detail** (pixel-perfect implementations)  
✅ **Availability** for 8-12 week engagement (part-time OK)

### Strong Preference:
⭐ Background in **music production** or audio engineering  
⭐ Experience with **Windows Fluent Design System**  
⭐ Published **UI component libraries** or design systems  
⭐ **WinUI 3 / WPF / UWP** development experience  
⭐ Understanding of **accessibility** and inclusive design

---

## 🚀 Why Join This Project?

✨ **Creative freedom:** Design a next-generation music production tool  
✨ **Modern tech:** Work with cutting-edge WinUI 3 and .NET 9.0  
✨ **Impact:** Build tools used by musicians and producers worldwide  
✨ **Portfolio piece:** High-quality, production-grade desktop application  
✨ **Remote flexibility:** Work from anywhere, flexible hours  
✨ **Strong compensation:** Competitive rates for specialized skills

---

## 📧 How to Apply

**Email:** [your-email@domain.com]  
**Subject:** `DirectAI UI/UX - [Your Role]`

**Include:**
1. **Portfolio** (Behance, Dribbble, personal website)
   - **MUST include:** Music/audio software projects
   - **Bonus:** Dark UI themes, desktop applications
2. **Resume/CV** (PDF)
3. **Cover Letter** (2-3 paragraphs):
   - Why you're excited about music software design
   - Relevant experience with audio/creative tools
   - Availability and hourly rate
4. **Design Sample** (optional but highly valued):
   - Redesign mockup of our current MixingPage
   - Custom audio player interface
   - Timeline component design

---

## 📚 Current Codebase Reference

### Key Files to Review:
- **Main Window:** `src/MusicPlatform.WinUI/MainWindow.xaml`
- **Mixing Page:** `src/MusicPlatform.WinUI/Views/MixingPage.xaml`
- **Audio Library:** `src/MusicPlatform.WinUI/Views/AudioLibraryPage.xaml`
- **ViewModels:** `src/MusicPlatform.WinUI/ViewModels/`
- **Design Docs:** `docs/LIBRARY_UI_COMPLETE.md`

### WinUI 3 Constraints (Important!):
⚠️ **No `RelativeSource` binding** - Use `ElementName` instead  
⚠️ **No `BorderDashArray`** - Solid borders only  
⚠️ **ScrollViewer blocks drag-drop** - Attach handlers to child elements  
⚠️ **Limited gradient support** - Simple gradients only  

### Architecture:
- **MVVM pattern** with CommunityToolkit.Mvvm
- **`[ObservableProperty]`** for properties
- **`[RelayCommand]`** for commands
- **ElementName binding** for parent DataContext access

---

## 🎯 Success Metrics

### Design Quality:
- ⭐ 9+ rating from user testing sessions
- ⭐ Design system completeness (100% components documented)
- ⭐ Accessibility compliance (WCAG AA)

### Technical Quality:
- ⚡ Smooth 60fps scrolling and animations
- ⚡ <100ms response time for drag-and-drop
- ⚡ <500ms page load times

### User Experience:
- 🎵 90%+ task completion rate in usability tests
- 🎵 <5 clicks to complete core workflows
- 🎵 Positive feedback from professional music producers

---

## 🔗 Reference Materials

### Design Inspiration:
- [SUNO Studio](https://suno.com/) - AI music generation UI
- [Ableton Live](https://www.ableton.com/) - Professional DAW
- [Splice](https://splice.com/) - Sample library and collaboration
- [Soundtrap](https://www.soundtrap.com/) - Online DAW

### WinUI 3 Resources:
- [WinUI 3 Gallery](https://github.com/microsoft/WinUI-Gallery)
- [Windows Design Guidelines](https://learn.microsoft.com/en-us/windows/apps/design/)
- [WinUI 3 Documentation](https://learn.microsoft.com/en-us/windows/apps/winui/winui3/)
- [Fluent Design System](https://www.microsoft.com/design/fluent/)

### Music Production UX:
- [LANDR Blog](https://blog.landr.com/) - Music production insights
- [Sound on Sound](https://www.soundonsound.com/) - Audio software reviews
- [Gearslutz](https://gearspace.com/) - Producer community

---

**Project Status:** 🟢 Actively Hiring  
**Last Updated:** October 27, 2025  
**Expected Start Date:** November 2025

---

*We're building a groundbreaking AI music platform with a desktop experience that musicians will love. If you're passionate about music technology and want to create something truly special, we want to hear from you!*

**Apply today and help us build the future of music creation.** 🎸🎹🥁🎤
