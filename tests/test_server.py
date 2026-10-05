"""Public MCP proxies, with scheduling isolated from sandbox async IPC."""
import asyncio
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        activity=Mock();activity.lock=threading.RLock();activity.stopped.is_set.return_value=False
        self.state_patch=patch.object(server,'_session_state','active');self.state_patch.start()
        self.activity_patch=patch.object(server,'_activity',activity);self.activity_patch.start()
        self.worker=Mock()
        self.worker.epoch.return_value=0
        self.worker.call.return_value={'ok':True}
        self.worker_patch=patch.object(server,'worker',return_value=self.worker);self.worker_patch.start()
        async def inline(function,*args,**kwargs):return function(*args,**kwargs)
        self.thread_patch=patch.object(server.asyncio,'to_thread',side_effect=inline);self.thread_patch.start()
    def tearDown(self):self.thread_patch.stop();self.worker_patch.stop();self.activity_patch.stop();self.state_patch.stop()

    def test_every_proxy_forwards_exact_arguments_and_errors(self):
        calls=[('list_apps',{}),('list_windows',{}),('bind_window',{'window_id':'123'}),('activate_window',{}),
            ('wait_for_window_state',{'state':'stable','timeout':3}),('computer_status',{}),('desktop_diagnostics',{}),('click',{'x':1,'y':2,'button':'left','clicks':1}),
            ('move_mouse',{'x':1,'y':2}),('drag',{'start_x':1,'start_y':1,'end_x':2,'end_y':2,'duration':0.5}),
            ('type_text',{'text':'日本😀','input_mode':'paced'}),('press_keys',{'keys':['ctrl','a']}),('scroll',{'amount':1,'x':1,'y':2}),
            ('inspect_ui',{'max_nodes':150,'max_depth':8}),
            ('find_elements',{'name':'Save','role':'','exact':False,'max_nodes':500,'max_depth':20}),
            ('read_element',{'element_id':'id'}),('act_on_element',{'element_id':'id','action':'activate'})]
        for name,args in calls:
            with self.subTest(tool=name):
                self.worker.call.side_effect=None
                self.assertEqual(asyncio.run(getattr(server,name)(**args)),{'ok':True})
                self.worker.call.assert_called_with(name,args,epoch=0)
                self.worker.call.side_effect=TimeoutError('deadline exceeded')
                with self.assertRaises(TimeoutError):asyncio.run(getattr(server,name)(**args))

    def test_screenshot_includes_provenance_and_image(self):
        self.worker.call.return_value={'png':b'png','provenance':{'window_id':'123','desktop_capture_used':False}}
        result=asyncio.run(server.screenshot())
        self.assertEqual([block.type for block in result],['text','image'])
        self.assertIn('123',result[0].text)

    def test_cancel_kills_worker_and_reports_uncertainty(self):
        self.worker.cancel.return_value=True
        result=asyncio.run(server.cancel_pending())
        self.worker.cancel.assert_called_once_with()
        self.assertTrue(result['target_discarded'])

    def test_invalid_search_and_wait_do_not_dispatch(self):
        with self.assertRaises(ValueError):asyncio.run(server.find_elements())
        for seconds in [-1,4,float('nan')]:
            with self.assertRaises(ValueError):asyncio.run(server.wait(seconds))
        self.worker.call.assert_not_called()
        self.assertEqual(asyncio.run(server.wait(0)),{'waited':0})

    def test_mcp_task_cancellation_kills_matching_worker_generation(self):
        async def scheduler(function,*args,**kwargs):
            if function == self.worker.call: raise asyncio.CancelledError()
            return function(*args,**kwargs)
        with patch.object(server.asyncio,'to_thread',side_effect=scheduler):
            with self.assertRaises(asyncio.CancelledError):asyncio.run(server.computer_status())
        self.worker.cancel.assert_called_once_with(epoch=0)

    def test_local_stop_rejects_before_dispatch(self):
        import threading
        activity=Mock();activity.lock=threading.Lock()
        activity.check.side_effect=RuntimeError('stopped')
        with patch.object(server,'_activity',activity):
            with self.assertRaisesRegex(RuntimeError,'stopped'):
                asyncio.run(server.list_windows())
        self.worker.call.assert_not_called()

    def test_cleanup_stops_input_before_hiding_indicator(self):
        events=[]
        activity=Mock();activity.close.side_effect=lambda:events.append('hide')
        self.worker.cancel.side_effect=lambda:events.append('cancel')
        with patch.object(server,'_worker',self.worker),patch.object(server,'_activity',activity):
            server.cleanup()
        self.assertEqual(events,['cancel','hide'])

    def test_wait_rejects_local_stop_even_for_zero_seconds(self):
        import threading
        activity=Mock();activity.lock=threading.Lock()
        activity.check.side_effect=RuntimeError('stopped')
        with patch.object(server,'_activity',activity):
            with self.assertRaisesRegex(RuntimeError,'stopped'):
                asyncio.run(server.wait(0))
        self.worker.call.assert_not_called()

    def test_wait_aborts_stop_during_sleep(self):
        import threading
        activity=Mock();activity.lock=threading.Lock()
        activity.check.side_effect=[None,None,None,RuntimeError('stopped')]
        async def immediate(seconds):pass
        with patch.object(server,'_activity',activity),patch.object(server.asyncio,'sleep',side_effect=immediate):
            with self.assertRaisesRegex(RuntimeError,'stopped'):
                asyncio.run(server.wait(.1))

    def test_wait_detects_stop_and_resume_between_polls(self):
        import threading
        activity=Mock();activity.lock=threading.Lock()
        self.worker.epoch.side_effect=[0,0,1]
        async def immediate(seconds):pass
        with patch.object(server,'_activity',activity),patch.object(server.asyncio,'sleep',side_effect=immediate):
            with self.assertRaisesRegex(RuntimeError,'generation changed'):
                asyncio.run(server.wait(.1))


    def test_stop_after_admission_check_fences_old_epoch(self):
        import threading
        activity=Mock();activity.lock=threading.Lock();native_dispatch=Mock()
        def stop_after_check():self.worker.epoch.return_value=1
        checks=[]
        def check():
            checks.append(1)
            if len(checks)==2:stop_after_check()
        activity.check.side_effect=check
        def fenced_call(method,args,epoch):
            if epoch!=self.worker.epoch.return_value:raise RuntimeError('cancelled before dispatch')
            return native_dispatch()
        self.worker.call.side_effect=fenced_call
        with patch.object(server,'_activity',activity):
            with self.assertRaisesRegex(RuntimeError,'cancelled before dispatch'):
                asyncio.run(server.computer_status())
        native_dispatch.assert_not_called()
        self.worker.call.assert_called_once_with('computer_status',{},epoch=0)
