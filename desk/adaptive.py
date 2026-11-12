"""Explicit interaction evidence only. Inactivity is not dislike or consent."""
def interaction_profile(state):
    events = state.get('interactionEvents', [])[-6:]
    skips = sum(e.get('type') == 'skip' for e in events)
    short = sum(e.get('type') == 'answer' and 0 < e.get('length', 0) < 60 for e in events)
    unanswered = [e['questionId'] for e in events if e.get('type') == 'skip']
    mode = 'visual-choice' if skips >= 2 else 'short-scene' if skips or short >= 2 else 'scene'
    guidance = {
        'scene': 'Present 4-5 related scene-grounded questions per round. Preserve the original assignment waypoint.',
        'short-scene': 'Present 4-5 short concrete questions about one visible detail in the existing reference image. Offer at most two optional examples. Do not repeat the skipped question.',
        'visual-choice': 'Repeated explicit skips: change the interaction. Present 4-5 very short questions comparing two concrete visible scene options, plus free writing. Avoid abstract lore, biography, motivation essays and repeated skipped topics. User can defer all choices. Do not infer rejection or approval.'
    }[mode]
    return {'mode': mode, 'recentSkips': skips, 'recentShortAnswers': short, 'deferredQuestions': unanswered, 'guidance': guidance, 'basis': 'explicit skip events and submitted-answer lengths; no inference from elapsed time'}
