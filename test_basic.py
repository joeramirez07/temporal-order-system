#!/usr/bin/env python3
"""
Basic test to verify our imports work without Temporal server
"""

import sys
import asyncio

def test_imports():
    """Test that all our modules import correctly"""
    print("Testing imports...")
    try:
        # Test each import individually to see where it fails
        print("  - Importing database...")
        from src.database import Database
        
        print("  - Importing business functions...")
        from src.business_functions import flaky_call
        
        print("  - Importing activities...")
        from src.activities import receive_order_activity
        
        print("  - Importing workflows...")
        from src.workflows import OrderWorkflow, ShippingWorkflow
        
        print("✅ All imports successful!")
        return True, OrderWorkflow, ShippingWorkflow, flaky_call
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False, None, None, None

async def test_flaky_call(flaky_call_func):
    """Test the flaky_call function with timeout"""
    try:
        # This should either raise an error or timeout
        await asyncio.wait_for(flaky_call_func(), timeout=2.0)
        print("✅ flaky_call completed without error")
    except asyncio.TimeoutError:
        print("✅ flaky_call timed out as expected")
    except RuntimeError as e:
        print(f"✅ flaky_call raised error as expected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_workflow_structure(OrderWorkflow, ShippingWorkflow):
    """Test workflow class structure"""
    try:
        # Test that we can instantiate workflows
        order_wf = OrderWorkflow()
        shipping_wf = ShippingWorkflow()
        
        # Test that they have required methods
        assert hasattr(order_wf, 'cancel_order')
        assert hasattr(order_wf, 'approve_order')
        assert hasattr(order_wf, 'update_address')
        assert hasattr(order_wf, 'get_status')
        
        print("✅ Workflow structure looks good!")
        return True
    except Exception as e:
        print(f"❌ Workflow structure test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing basic functionality...\n")
    
    # Test imports and get the classes
    import_success, OrderWorkflow, ShippingWorkflow, flaky_call_func = test_imports()
    
    success = import_success
    
    if import_success:
        success &= test_workflow_structure(OrderWorkflow, ShippingWorkflow)
        
        print("\n🧪 Testing flaky_call function...")
        asyncio.run(test_flaky_call(flaky_call_func))
    
    if success:
        print("\n🎉 All basic tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)