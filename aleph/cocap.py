"""Coherence Capacity (CoCap) Module.

This module implements the Coherence Capacity Theorem for memory-constrained systems.
It provides utilities to:
- Estimate skeleton entropy H(Z) for stored content
- Calculate effective capacity C based on memory constraints
- Monitor coherence and trigger management actions when approaching limits
- Manage memory through compression, offloading, or selective forgetting

Mathematical Foundation:
    H(Z) = h2(α) + (1-α) * log2(L)  bits/step
    
Where:
- α = introduction rate (probability of new entity)
- L = number of active entities (conceptual "slots" in use)
- h2(x) = binary entropy function: -x*log2(x) - (1-x)*log2(1-x)

The coherence-capacity theorem states:
- If H(Z) < C: arbitrarily low error is achievable
- If H(Z) > C: coherence error is bounded away from zero

This creates a phase transition at H(Z) ≈ C.

For practical implementation with natural language content:
- H(Z) is approximated from unique terms, entities, and relations
- C is set by the number of conceptual "slots" available
- Management strategies are triggered at configurable thresholds (e.g., 85% of C)

Example:
    >>> from aleph.cocap import CoCapMonitor, estimate_entropy
    >>> monitor = CoCapMonitor(slot_count=16, warning_threshold=0.85)
    >>> content = "Alice found a bug in the authentication module..."
    >>> H_Z = estimate_entropy(content)
    >>> status = monitor.check_status(H_Z)
    >>> if status.needs_management:
    ...     monitor.suggest_action()
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum


# -----------------------------------------------------------------------------
# Mathematical Utilities
# -----------------------------------------------------------------------------

def binary_entropy(x: float) -> float:
    """Binary entropy function h2(x) = -x*log2(x) - (1-x)*log2(1-x).
    
    Args:
        x: Probability value in [0, 1]
        
    Returns:
        Entropy in bits. Returns 0 for x=0 or x=1.
        
    Examples:
        >>> binary_entropy(0.5)
        1.0
        >>> binary_entropy(0.0)
        0.0
    """
    if x <= 0 or x >= 1:
        return 0.0
    return -x * math.log2(x) - (1 - x) * math.log2(1 - x)


def estimate_h_z(alpha: float, active_entities: int | float) -> float:
    """Estimate skeleton entropy rate H(Z).
    
    This follows the pointer machine model:
    H(Z) = h2(α) + (1-α) * log2(L)
    
    Args:
        alpha: Introduction rate (probability new entity is introduced)
        active_entities: Number of active entities L (can be float for average)
        
    Returns:
        Entropy rate in bits
        
    Examples:
        >>> estimate_h_z(0.2, 8)  # 20% new entities, 8 active
        3.0
    """
    h_intro = binary_entropy(alpha)
    h_ref = (1 - alpha) * math.log2(active_entities) if active_entities > 0 else 0
    return h_intro + h_ref


def capacity_from_slots(slot_count: int, redundancy_factor: float = 1.0) -> float:
    """Calculate effective capacity C from slot count.
    
    For a discrete slot system with K slots, the maximum information
    that can be reliably stored is approximately log2(K) bits, accounting
    for error correction overhead.
    
    Args:
        slot_count: Number of available memory slots K
        redundancy_factor: Fraction of capacity available after error correction
                          (e.g., 0.9 means 90% usable)
                          
    Returns:
        Capacity C in bits
        
    Examples:
        >>> capacity_from_slots(16)
        4.0
        >>> capacity_from_slots(32)
        5.0
        >>> capacity_from_slots(16, redundancy_factor=0.8)
        3.2
    """
    if slot_count <= 0:
        return 0.0
    raw_capacity = math.log2(slot_count)
    return raw_capacity * redundancy_factor


# -----------------------------------------------------------------------------
# Entropy Estimation for Natural Language
# -----------------------------------------------------------------------------

# Common English stop words to exclude from entity counting
STOP_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else', 'when',
    'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
    'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
    'further', 'then', 'once', 'here', 'there', 'where', 'why', 'how',
    'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    's', 't', 'can', 'will', 'just', 'don', 'should', 'now',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'having', 'do', 'does', 'did', 'doing', 'would', 'could', 'ought',
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
    'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
    'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
    'that', 'these', 'those', 'am', 'as', 'of', 'until', 'while', 'because',
    'although', 'since', 'unless', 'also', 'both', 'either', 'neither',
    'notonly', 'whether', 'get', 'got', 'gets', 'getting', 'go', 'goes',
    'going', 'went', 'gone', 'make', 'makes', 'making', 'made', 'see',
    'sees', 'seeing', 'saw', 'seen', 'know', 'knows', 'knowing', 'knew',
    'known', 'think', 'thinks', 'thinking', 'thought', 'take', 'takes',
    'taking', 'took', 'taken', 'come', 'comes', 'coming', 'came', 'want',
    'wants', 'wanting', 'wanted', 'use', 'uses', 'using', 'used', 'find',
    'finds', 'finding', 'found', 'give', 'gives', 'giving', 'gave', 'given',
    'tell', 'tells', 'telling', 'told', 'may', 'might', 'must', 'shall',
    'need', 'needs', 'needing', 'needed'
})


def extract_entities(text: str) -> list[str]:
    """Extract potential entities from text.
    
    Entities are identified as:
    1. Capitalized words (excluding start of sentences)
    2. Multi-word capitalized phrases (e.g., "Machine Learning")
    3. Words after definite articles in technical contexts
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of identified entities
    """
    entities = []
    
    # Pattern for capitalized words/phrases (excluding sentence starts)
    # This is a simplified heuristic - a full NER system would be better
    words = text.split()
    
    for i, word in enumerate(words):
        # Skip if it's a stop word or number
        if word.lower() in STOP_WORDS or word.isdigit():
            continue
            
        # Check for capitalized word (potential entity)
        if word and word[0].isupper():
            # Build multi-word entity
            entity = word
            j = i + 1
            while j < len(words):
                next_word = words[j]
                # Stop if it's a stop word, number, or lowercase (except at sentence start)
                if (next_word.lower() in STOP_WORDS or 
                    next_word.isdigit() or 
                    (next_word and next_word[0].islower() and j > 0)):
                    break
                # Continue if capitalized (continuation of entity name)
                if next_word and next_word[0].isupper():
                    entity += " " + next_word
                    j += 1
                else:
                    break
            
            if len(entity) > 1:  # Skip single-character entities
                entities.append(entity)
    
    return entities


def count_unique_concepts(text: str) -> int:
    """Count unique conceptual units in text.
    
    Concepts are approximated by:
    1. Non-stop-word tokens
    2. Normalized to lowercase
    
    Args:
        text: Input text to analyze
        
    Returns:
        Approximate count of unique concepts
    """
    # Tokenize and normalize
    tokens = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())
    
    # Filter stop words
    concepts = {token for token in tokens if token not in STOP_WORDS and len(token) > 1}
    
    return len(concepts)


def estimate_redundancy(text: str) -> float:
    """Estimate information redundancy in text.
    
    Redundancy is estimated from:
    1. Repetition of key terms
    2. Self-reference patterns
    3. Parenthetical explanations
    
    Args:
        text: Input text to analyze
        
    Returns:
        Redundancy factor in [0, 1], where 1 = highly redundant
    """
    tokens = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', text.lower())
    if len(tokens) < 10:
        return 0.0
    
    # Count repetitions
    token_counts: dict[str, int] = {}
    for token in tokens:
        if token not in STOP_WORDS and len(token) > 2:
            token_counts[token] = token_counts.get(token, 0) + 1
    
    if not token_counts:
        return 0.0
    
    # Calculate repetition ratio
    repeated_tokens = sum(1 for count in token_counts.values() if count > 1)
    
    # Check for self-reference patterns
    self_ref_count = len(re.findall(r'\b(self|itself|himself|herself|themselves|this|that|it)\b', text.lower()))
    
    # Check for parenthetical explanations (often redundant)
    paren_count = len(re.findall(r'\([^)]*\)', text))
    
    # Combine signals
    repetition_ratio = repeated_tokens / len(token_counts)
    self_ref_ratio = self_ref_count / len(tokens)
    paren_ratio = paren_count / len(tokens)
    
    redundancy = (repetition_ratio * 0.5 + 
                  self_ref_ratio * 0.3 + 
                  paren_ratio * 0.2)
    
    return min(1.0, redundancy)


def estimate_skeleton_entropy(
    text: str,
    alpha: float | None = None,
    slot_count: int | None = None,
) -> dict:
    """Estimate skeleton entropy for natural language content.
    
    This provides a practical approximation of H(Z) for arbitrary text.
    The algorithm uses:
    - Unique concepts as a proxy for active entities
    - Introduction rate estimated from text structure
    - Redundancy to adjust effective entropy
    
    Args:
        text: Content to analyze
        alpha: Optional introduction rate override (estimated if None)
        slot_count: Optional slot count for reference
        
    Returns:
        Dictionary with entropy estimates and metadata
    """
    # Count unique concepts (proxy for active entities L)
    unique_concepts = count_unique_concepts(text)
    entities = extract_entities(text)
    unique_entities = len(set(entities))
    
    # Estimate L (effective active entities)
    L = max(1, unique_concepts // 5)  # Rough heuristic
    
    # Estimate alpha from text structure
    if alpha is None:
        # More capital letters at non-sentence starts = higher introduction
        words = text.split()
        capitalized = sum(1 for w in words if w and w[0].isupper())
        if words:
            alpha = min(0.5, capitalized / len(words) / 3)  # Scaled heuristic
        else:
            alpha = 0.1
    
    # Calculate H(Z)
    H_Z = estimate_h_z(alpha, L)
    
    # Adjust for redundancy (redundant content has lower effective entropy)
    redundancy = estimate_redundancy(text)
    H_Z_effective = H_Z * (1 - redundancy * 0.3)  # Up to 30% reduction
    
    # Estimate capacity if slot_count provided
    capacity_info = {}
    if slot_count is not None:
        C = capacity_from_slots(slot_count)
        slack = C - H_Z_effective
        capacity_info = {
            'capacity': C,
            'slack': slack,
            'utilization': H_Z_effective / C if C > 0 else float('inf'),
            'phase': 'below' if slack > 0.5 else ('near' if slack >= 0 else 'above')
        }
    
    return {
        'H_Z_raw': H_Z,
        'H_Z_effective': H_Z_effective,
        'alpha_estimated': alpha,
        'L_estimated': L,
        'unique_concepts': unique_concepts,
        'unique_entities': unique_entities,
        'redundancy': redundancy,
        **capacity_info
    }


# -----------------------------------------------------------------------------
# Capacity Monitor
# -----------------------------------------------------------------------------

class CapacityPhase(Enum):
    """Phases of coherence capacity utilization."""
    
    HEALTHY = "healthy"      # Well below capacity, coherent
    NEAR = "near"            # Approaching capacity, monitoring
    CRITICAL = "critical"    # At capacity, errors likely
    OVERLOADED = "overloaded"  # Above capacity, coherence broken


@dataclass
class CapacityStatus:
    """Current capacity utilization status."""
    
    phase: CapacityPhase
    H_Z_effective: float
    capacity: float
    slack: float
    utilization_percent: float
    needs_management: bool
    suggested_actions: list[str]
    confidence: float  # How confident we are in the estimate


@dataclass
class CoCapConfig:
    """Configuration for CoCap monitor."""
    
    slot_count: int = 16
    warning_threshold: float = 0.75  # Trigger warning at this utilization
    critical_threshold: float = 0.90  # Trigger critical at this utilization
    redundancy_factor: float = 0.9  # Capacity after error correction
    alpha_estimate: float | None = None  # Override alpha estimation
    enabled: bool = True


class CoCapMonitor:
    """Coherence Capacity Monitor for memory-constrained systems.
    
    This monitor tracks skeleton entropy H(Z) against capacity C and
    provides alerts and management suggestions when approaching limits.
    
    Example:
        >>> monitor = CoCapMonitor(slot_count=16, warning_threshold=0.8)
        >>> status = monitor.check_status("Alice found a bug...")
        >>> print(status.phase)
        CapacityPhase.HEALTHY
    """
    
    def __init__(
        self,
        slot_count: int = 16,
        config: CoCapConfig | None = None,
    ):
        """Initialize the CoCap monitor.
        
        Args:
            slot_count: Number of conceptual slots available
            config: Optional configuration object
        """
        self.config = config or CoCapConfig(slot_count=slot_count)
        self._history: list[dict] = []
        self._session_H_Z: float = 0.0
        self._session_weight: float = 0.0
        
    def check_status(self, content: str) -> CapacityStatus:
        """Check capacity status for given content.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Current capacity status with suggestions
        """
        if not self.config.enabled:
            return CapacityStatus(
                phase=CapacityPhase.HEALTHY,
                H_Z_effective=0.0,
                capacity=self.capacity,
                slack=self.capacity,
                utilization_percent=0.0,
                needs_management=False,
                suggested_actions=[],
                confidence=1.0
            )
        
        # Estimate entropy
        estimate = estimate_skeleton_entropy(
            content,
            alpha=self.config.alpha_estimate,
            slot_count=self.config.slot_count
        )
        
        H_Z = estimate['H_Z_effective']
        self._session_H_Z = self._session_H_Z * 0.9 + H_Z * 0.1
        self._session_weight += 1.0
        
        # Calculate utilization
        capacity = self.capacity
        utilization = H_Z / capacity if capacity > 0 else float('inf')
        slack = capacity - H_Z
        
        # Determine phase
        if utilization >= self.config.critical_threshold:
            phase = CapacityPhase.CRITICAL
        elif utilization >= self.config.warning_threshold:
            phase = CapacityPhase.NEAR
        else:
            phase = CapacityPhase.HEALTHY
        
        # Generate suggestions based on phase
        suggested_actions = self._get_suggestions(phase, estimate)
        
        # Track history
        self._history.append({
            'H_Z': H_Z,
            'capacity': capacity,
            'utilization': utilization,
            'phase': phase.value,
            'content_length': len(content)
        })
        
        return CapacityStatus(
            phase=phase,
            H_Z_effective=H_Z,
            capacity=capacity,
            slack=slack,
            utilization_percent=utilization * 100,
            needs_management=phase in (CapacityPhase.NEAR, CapacityPhase.CRITICAL, CapacityPhase.OVERLOADED),
            suggested_actions=suggested_actions,
            confidence=min(1.0, estimate.get('unique_concepts', 1) / max(1, estimate.get('unique_entities', 1)))
        )
    
    def check_session_status(self) -> CapacityStatus:
        """Check status based on accumulated session entropy."""
        if not self.config.enabled:
            return CapacityStatus(
                phase=CapacityPhase.HEALTHY,
                H_Z_effective=0.0,
                capacity=self.capacity,
                slack=self.capacity,
                utilization_percent=0.0,
                needs_management=False,
                suggested_actions=[],
                confidence=1.0
            )
        
        H_Z = self._session_H_Z
        capacity = self.capacity
        utilization = H_Z / capacity if capacity > 0 else float('inf')
        slack = capacity - H_Z
        
        if utilization >= self.config.critical_threshold:
            phase = CapacityPhase.CRITICAL
        elif utilization >= self.config.warning_threshold:
            phase = CapacityPhase.NEAR
        else:
            phase = CapacityPhase.HEALTHY
        
        return CapacityStatus(
            phase=phase,
            H_Z_effective=H_Z,
            capacity=capacity,
            slack=slack,
            utilization_percent=utilization * 100,
            needs_management=phase in (CapacityPhase.NEAR, CapacityPhase.CRITICAL, CapacityPhase.OVERLOADED),
            suggested_actions=self._get_suggestions(phase, {'H_Z_effective': H_Z}),
            confidence=min(1.0, self._session_weight / 10)
        )
    
    def _get_suggestions(self, phase: CapacityPhase, estimate: dict) -> list[str]:
        """Get management suggestions based on current phase."""
        suggestions = []
        
        H_Z = estimate.get('H_Z_effective', 0)
        redundancy = estimate.get('redundancy', 0)
        
        if phase == CapacityPhase.HEALTHY:
            if H_Z < self.capacity * 0.5:
                suggestions.append("System has ample capacity for current load.")
        elif phase == CapacityPhase.NEAR:
            suggestions.append("Approaching coherence capacity. Consider:")
            if redundancy > 0.3:
                suggestions.append("- Removing redundant explanations")
            suggestions.append("- Summarizing earlier context")
            suggestions.append("- Consolidating related concepts")
        else:  # CRITICAL or OVERLOADED
            suggestions.append("CRITICAL: Coherence at risk. Immediate action needed:")
            suggestions.append("- Summarize and compress current context")
            suggestions.append("- Offload non-essential details to external storage")
            suggestions.append("- Consider starting a new session with summarized context")
        
        return suggestions
    
    @property
    def capacity(self) -> float:
        """Get current capacity in bits."""
        return capacity_from_slots(
            self.config.slot_count,
            self.config.redundancy_factor
        )
    
    @property
    def history(self) -> list[dict]:
        """Get history of capacity checks."""
        return list(self._history)
    
    def reset_session(self) -> None:
        """Reset session-level tracking."""
        self._session_H_Z = 0.0
        self._session_weight = 0.0


# -----------------------------------------------------------------------------
# Memory Management Strategies
# -----------------------------------------------------------------------------

@dataclass
class ManagementAction:
    """A memory management action to take."""
    
    action_type: str  # 'compress', 'offload', 'forget', 'summarize'
    priority: int  # Higher = more urgent
    description: str
    estimated_savings: float  # Bits of capacity freed
    target: str  # What to target (context, session, etc.)


def suggest_management(
    status: CapacityStatus,
    content: str,
    min_importance: float = 0.5,
) -> list[ManagementAction]:
    """Suggest memory management actions based on current status.
    
    Args:
        status: Current capacity status
        content: Current context content
        min_importance: Minimum importance threshold for keeping content
        
    Returns:
        List of suggested management actions
    """
    actions = []
    
    if not status.needs_management:
        return actions
    
    # Estimate potential savings from different strategies
    current_H_Z = status.H_Z_effective
    target_H_Z = status.capacity * 0.7
    savings_needed = current_H_Z - target_H_Z
    
    if savings_needed <= 0:
        return actions
    
    # Suggest compression if redundancy is high
    redundancy = estimate_redundancy(content)
    if redundancy > 0.2:
        compression_ratio = redundancy * 0.5  # Can reduce redundancy by ~50%
        estimated_bits = current_H_Z * compression_ratio
        if estimated_bits > 0:
            actions.append(ManagementAction(
                action_type='compress',
                priority=1 if redundancy > 0.4 else 2,
                description=f"Remove redundant content (redundancy: {redundancy:.1%})",
                estimated_savings=min(estimated_bits, savings_needed),
                target='redundant_content'
            ))
    
    # Suggest summarization for old content
    actions.append(ManagementAction(
        action_type='summarize',
        priority=3 if status.phase == CapacityPhase.CRITICAL else 2,
        description="Summarize earlier context to free capacity",
        estimated_savings=savings_needed * 0.3,
        target='earlier_context'
    ))
    
    # Suggest offloading if still over capacity
    if status.phase == CapacityPhase.CRITICAL:
        actions.append(ManagementAction(
            action_type='offload',
            priority=1,
            description="Offload detailed content to external memory",
            estimated_savings=savings_needed * 0.5,
            target='detailed_content'
        ))
    
    # Sort by priority (lower number = higher priority)
    actions.sort(key=lambda a: a.priority)
    
    return actions


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------

def estimate_entropy(content: str) -> float:
    """Quick estimate of skeleton entropy for content.
    
    Args:
        content: Text content to analyze
        
    Returns:
        Estimated H(Z) in bits
    """
    result = estimate_skeleton_entropy(content)
    return result['H_Z_effective']


def capacity_status(
    content: str,
    slot_count: int = 16,
    warning_threshold: float = 0.75,
) -> CapacityStatus:
    """Quick capacity status check for content.
    
    Args:
        content: Text content to analyze
        slot_count: Number of available slots
        warning_threshold: Threshold for warning
        
    Returns:
        Capacity status
    """
    config = CoCapConfig(
        slot_count=slot_count,
        warning_threshold=warning_threshold
    )
    monitor = CoCapMonitor(config=config)
    return monitor.check_status(content)
