
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
import uvicorn
from typing import Dict, List, Optional
import datetime

app = FastAPI(title="Routing Engine Service")

class RoutingRequest(BaseModel):
    doc_id: str
    doc_type: str
    department: str
    priority: str
    content_summary: Optional[str] = None
    file_size: Optional[int] = None
    user_department: Optional[str] = None

class RoutingResponse(BaseModel):
    doc_id: str
    assignee: str
    department: str
    priority: str
    routing_reason: str
    estimated_processing_time: str
    routing_status: str
    escalation_needed: bool

class DepartmentRule(BaseModel):
    department: str
    assignee: str
    priority_boost: int
    max_capacity: int
    specializations: List[str]
    processing_time: str

# Department routing rules
DEPARTMENT_RULES = {
    'hr': DepartmentRule(
        department='hr',
        assignee='hr_team',
        priority_boost=1,
        max_capacity=50,
        specializations=['employee', 'personnel', 'benefits', 'recruitment', 'training'],
        processing_time='1-2 business days'
    ),
    'finance': DepartmentRule(
        department='finance',
        assignee='finance_team',
        priority_boost=2,
        max_capacity=30,
        specializations=['invoice', 'payment', 'budget', 'expense', 'financial'],
        processing_time='3-5 business days'
    ),
    'legal': DepartmentRule(
        department='legal',
        assignee='legal_team',
        priority_boost=3,
        max_capacity=20,
        specializations=['contract', 'agreement', 'compliance', 'litigation', 'policy'],
        processing_time='5-10 business days'
    ),
    'it': DepartmentRule(
        department='it',
        assignee='it_team',
        priority_boost=2,
        max_capacity=40,
        specializations=['system', 'network', 'security', 'software', 'technical'],
        processing_time='1-3 business days'
    ),
    'sales': DepartmentRule(
        department='sales',
        assignee='sales_team',
        priority_boost=2,
        max_capacity=35,
        specializations=['proposal', 'quote', 'customer', 'deal', 'opportunity'],
        processing_time='2-4 business days'
    ),
    'marketing': DepartmentRule(
        department='marketing',
        assignee='marketing_team',
        priority_boost=1,
        max_capacity=25,
        specializations=['campaign', 'brand', 'content', 'social', 'analytics'],
        processing_time='3-7 business days'
    ),
    'operations': DepartmentRule(
        department='operations',
        assignee='operations_team',
        priority_boost=1,
        max_capacity=30,
        specializations=['process', 'workflow', 'logistics', 'supply'],
        processing_time='2-5 business days'
    ),
    'support': DepartmentRule(
        department='support',
        assignee='support_team',
        priority_boost=2,
        max_capacity=45,
        specializations=['ticket', 'issue', 'complaint', 'feedback'],
        processing_time='1-2 business days'
    ),
    'procurement': DepartmentRule(
        department='procurement',
        assignee='procurement_team',
        priority_boost=1,
        max_capacity=20,
        specializations=['purchase', 'vendor', 'supplier', 'acquisition'],
        processing_time='5-10 business days'
    ),
    'product': DepartmentRule(
        department='product',
        assignee='product_team',
        priority_boost=1,
        max_capacity=25,
        specializations=['research', 'development', 'design', 'innovation'],
        processing_time='7-14 business days'
    ),
    'administration': DepartmentRule(
        department='administration',
        assignee='admin_team',
        priority_boost=0,
        max_capacity=15,
        specializations=['office', 'facility', 'maintenance', 'general'],
        processing_time='3-7 business days'
    ),
    'executive': DepartmentRule(
        department='executive',
        assignee='executive_team',
        priority_boost=3,
        max_capacity=10,
        specializations=['strategy', 'decision', 'leadership', 'board'],
        processing_time='1-3 business days'
    ),
    'general': DepartmentRule(
        department='general',
        assignee='general_team',
        priority_boost=0,
        max_capacity=100,
        specializations=['general', 'misc', 'other'],
        processing_time='5-10 business days'
    )
}

# Priority processing time adjustments
PRIORITY_TIME_ADJUSTMENTS = {
    'high': 0.5,    # 50% faster
    'medium': 1.0,  # Normal time
    'low': 1.5      # 50% slower
}

def calculate_processing_time(base_time: str, priority: str, file_size: int = None) -> str:
    """Calculate estimated processing time based on priority and file size"""
    try:
        # Extract base time range
        if '-' in base_time:
            min_time, max_time = base_time.split('-')
            min_days = int(min_time.strip())
            max_days = int(max_time.split()[0])
        else:
            min_days = max_days = int(base_time.split()[0])
        
        # Apply priority adjustment
        adjustment = PRIORITY_TIME_ADJUSTMENTS.get(priority, 1.0)
        min_days = max(1, int(min_days * adjustment))
        max_days = max(1, int(max_days * adjustment))
        
        # File size adjustment (for large files)
        if file_size and file_size > 10 * 1024 * 1024:  # > 10MB
            min_days += 1
            max_days += 2
        
        if min_days == max_days:
            return f"{min_days} business day{'s' if min_days > 1 else ''}"
        else:
            return f"{min_days}-{max_days} business days"
    
    except:
        return base_time

def determine_escalation(priority: str, department: str, doc_type: str) -> bool:
    """Determine if document needs escalation"""
    # High priority documents in critical departments need escalation
    critical_departments = ['legal', 'finance', 'executive']
    critical_doc_types = ['legal_document', 'financial_document', 'executive_document']
    
    if priority == 'high' and (department in critical_departments or doc_type in critical_doc_types):
        return True
    
    return False

def generate_routing_reason(department: str, doc_type: str, priority: str, specializations: List[str]) -> str:
    """Generate human-readable routing reason"""
    reasons = []
    
    # Department match
    if department != 'general':
        reasons.append(f"Document classified as {doc_type} matches {department} department expertise")
    
    # Priority consideration
    if priority == 'high':
        reasons.append("High priority classification requires expedited processing")
    elif priority == 'low':
        reasons.append("Low priority allows for standard processing queue")
    
    # Specialization match
    relevant_specs = [spec for spec in specializations if spec in doc_type.lower()]
    if relevant_specs:
        reasons.append(f"Team specializes in {', '.join(relevant_specs)}")
    
    return ". ".join(reasons) if reasons else "Standard routing based on document classification"

@app.get("/")
async def root():
    return {"message": "Routing Engine Service is running", "service": "routing_engine"}

@app.post("/route", response_model=RoutingResponse)
async def route_document(request: RoutingRequest):
    """Route document to appropriate department and assignee"""
    try:
        # Get department rule
        rule = DEPARTMENT_RULES.get(request.department, DEPARTMENT_RULES['general'])
        
        # Determine final priority (could be boosted)
        original_priority = request.priority
        priority_levels = {'low': 1, 'medium': 2, 'high': 3}
        current_level = priority_levels.get(original_priority, 2)
        boosted_level = min(3, current_level + (rule.priority_boost - 1))
        
        final_priority = {1: 'low', 2: 'medium', 3: 'high'}[boosted_level]
        
        # Calculate processing time
        estimated_time = calculate_processing_time(
            rule.processing_time, 
            final_priority, 
            request.file_size
        )
        
        # Determine escalation needs
        escalation_needed = determine_escalation(
            final_priority, 
            request.department, 
            request.doc_type
        )
        
        # Generate routing reason
        routing_reason = generate_routing_reason(
            request.department, 
            request.doc_type, 
            final_priority, 
            rule.specializations
        )
        
        return RoutingResponse(
            doc_id=request.doc_id,
            assignee=rule.assignee,
            department=rule.department,
            priority=final_priority,
            routing_reason=routing_reason,
            estimated_processing_time=estimated_time,
            routing_status="routed",
            escalation_needed=escalation_needed
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")

@app.get("/departments")
async def get_departments():
    """Get available departments and their capabilities"""
    return {
        dept_id: {
            "name": rule.department,
            "assignee": rule.assignee,
            "specializations": rule.specializations,
            "capacity": rule.max_capacity,
            "typical_processing_time": rule.processing_time
        }
        for dept_id, rule in DEPARTMENT_RULES.items()
    }

@app.get("/workload/{department}")
async def get_department_workload(department: str):
    """Get current workload for a department (mock data)"""
    rule = DEPARTMENT_RULES.get(department)
    if not rule:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Mock workload data
    import random
    current_load = random.randint(5, rule.max_capacity - 5)
    
    return {
        "department": department,
        "current_documents": current_load,
        "max_capacity": rule.max_capacity,
        "utilization_percentage": round((current_load / rule.max_capacity) * 100, 1),
        "status": "normal" if current_load < rule.max_capacity * 0.8 else "high"
    }

@app.post("/bulk-route")
async def bulk_route_documents(requests: List[RoutingRequest]):
    """Route multiple documents at once"""
    results = []
    
    for request in requests:
        try:
            result = await route_document(request)
            results.append(result)
        except Exception as e:
            results.append({
                "doc_id": request.doc_id,
                "error": str(e),
                "routing_status": "failed"
            })
    
    return {"results": results, "total_processed": len(results)}

@app.get("/ping")
async def ping():
    return {"message": "pong from Routing Engine Service"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
