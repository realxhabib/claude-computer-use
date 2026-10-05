"""Companions must never bootstrap through the active MCP main/stdio."""
import asyncio
import multiprocessing
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from claude_computer_use import companion_launch as launch
from claude_computer_use.companion_entry import probe
from claude_computer_use.signals import ProcessSignal, BoundedProcessLock


class CompanionLaunchTests(unittest.TestCase):
    def launch_context(self, handshake=True):
        parent=Mock();child=Mock();child.fileno.return_value=123
        parent.poll.return_value=handshake;parent.recv.return_value={'pid':456}
        raw=Mock();wrapper=Mock();wrapper.pid=456
        patches=[patch.object(launch.multiprocessing,'get_context',return_value=Mock(Pipe=Mock(return_value=(parent,child)))),
            patch.object(launch.os,'get_handle_inheritable',return_value=False,create=True),
            patch.object(launch.os,'set_handle_inheritable',create=True),
            patch.object(launch.subprocess,'STARTUPINFO',return_value=Mock(),create=True),
            patch.object(launch.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True),
            patch.object(launch.subprocess,'Popen',return_value=raw),
            patch.object(launch,'CompanionProcess',return_value=wrapper),
            patch.object(launch,'serialize_arguments',return_value=b'private payload')]
        mocks=[p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        return parent,child,raw,wrapper,mocks

    def test_private_handle_only_and_actual_pid_argument_transfer(self):
        parent,child,raw,wrapper,mocks=self.launch_context()
        result=launch.launch_windows_companion(probe,(),shutdown='signal')
        self.assertIs(result,wrapper)
        args,kwargs=mocks[5].call_args
        self.assertIn('claude_computer_use.companion_entry',args[0])
        self.assertEqual(kwargs['stdin'],launch.subprocess.DEVNULL)
        self.assertEqual(kwargs['stdout'],launch.subprocess.DEVNULL)
        self.assertTrue(kwargs['close_fds'])
        self.assertEqual(kwargs['startupinfo'].lpAttributeList,{'handle_list':[123]})
        self.assertEqual(mocks[2].call_args_list[-1].args,(123,False))
        wrapper.attach.assert_called_once_with(456)
        mocks[7].assert_called_once_with(probe,(),456,'signal',False)
        parent.send_bytes.assert_called_once_with(b'private payload')
        parent.close.assert_called_once()

    def test_handshake_timeout_kills_tree_before_returning(self):
        parent,child,raw,wrapper,mocks=self.launch_context(False)
        with self.assertRaisesRegex(RuntimeError,'handshake timed out'):
            launch.launch_windows_companion(probe,(),timeout=.1)
        wrapper.kill.assert_called_once();wrapper.join.assert_called_once_with(1)
        parent.send_bytes.assert_not_called();mocks[7].assert_not_called()

    def test_process_creation_failure_restores_inheritance_and_closes_pipe(self):
        parent,child,raw,wrapper,mocks=self.launch_context()
        mocks[5].side_effect=OSError('create process failed')
        with self.assertRaisesRegex(OSError,'create process failed'):
            launch.launch_windows_companion(probe,())
        self.assertEqual(mocks[2].call_args_list[-1].args,(123,False))
        parent.close.assert_called_once();child.close.assert_called_once()

    def test_malformed_handshake_is_rejected_and_tree_killed(self):
        parent,child,raw,wrapper,mocks=self.launch_context()
        parent.recv.return_value={'pid':True}
        with self.assertRaisesRegex(RuntimeError,'Invalid companion'):
            launch.launch_windows_companion(probe,())
        mocks[7].assert_not_called();wrapper.kill.assert_called_once()

    def test_foreign_pid_rejects_before_shared_handle_transfer(self):
        parent,child,raw,wrapper,mocks=self.launch_context()
        wrapper.attach.side_effect=RuntimeError('foreign PID')
        with self.assertRaisesRegex(RuntimeError,'foreign PID'):launch.launch_windows_companion(probe,())
        mocks[7].assert_not_called();wrapper.kill.assert_called_once()

    def test_serialization_error_restores_thread_local_context_and_closes_handle(self):
        from multiprocessing import context,reduction
        previous=context.get_spawning_popen()
        transfer=Mock()
        with patch.object(launch,'HandleTransfer',return_value=transfer),patch.object(reduction.ForkingPickler,'dumps',side_effect=ValueError('synthetic')):
            with self.assertRaises(ValueError):launch.serialize_arguments(probe,(),456)
        self.assertIs(context.get_spawning_popen(),previous)
        transfer.close.assert_called_once()

    def test_payload_is_bounded_below_windows_pipe_capacity(self):
        from multiprocessing import reduction
        transfer=Mock()
        with patch.object(launch,'HandleTransfer',return_value=transfer),patch.object(reduction.ForkingPickler,'dumps',return_value=b'x'*4097):
            with self.assertRaisesRegex(RuntimeError,'payload limit'):launch.serialize_arguments(probe,(),456)
        transfer.close.assert_called_once()

    def test_attach_requires_owned_interpreter_identity(self):
        wrapper=launch.CompanionProcess.__new__(launch.CompanionProcess)
        wrapper.root=Mock(pid=123);child=Mock(pid=456)
        wrapper.root.children.return_value=[child]
        child.is_running.return_value=True
        wrapper.attach(456);self.assertIs(wrapper.actual,child)
        with self.assertRaisesRegex(RuntimeError,'not in'):wrapper.attach(789)

    def test_non_windows_retains_spawn_path(self):
        ctx=Mock()
        with patch.object(launch.sys,'platform','darwin'):
            process=launch.start_companion(ctx,probe,(1,2))
        ctx.Process.assert_called_once_with(target=probe,args=(1,2),daemon=True)
        process.start.assert_called_once()


@unittest.skipUnless(sys.platform=='win32','Native Windows private companion bootstrap')
class WindowsCompanionTests(unittest.TestCase):
    def test_actual_pipe_shared_flags_values_and_lock_from_async_thread(self):
        async def run():
            ctx=multiprocessing.get_context('spawn')
            ready=ProcessSignal(ctx);shutdown=ProcessSignal(ctx)
            pid_value=ctx.RawValue('q',0);lock=BoundedProcessLock(ctx)
            process=await asyncio.to_thread(launch.launch_windows_companion,probe,
                (ready,shutdown,pid_value,lock),10,shutdown)
            try:
                self.assertTrue(await asyncio.to_thread(ready.wait,5))
                self.assertEqual(pid_value.value,process.pid)
                self.assertNotEqual(process.pid,os.getpid())
                shutdown.set();await asyncio.to_thread(process.join,2)
                self.assertFalse(process.is_alive())
            finally:
                if process.is_alive():process.kill();process.join(2)
        asyncio.run(run())
