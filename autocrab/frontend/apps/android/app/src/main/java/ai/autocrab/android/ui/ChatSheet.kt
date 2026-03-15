package ai.autocrab.android.ui

import androidx.compose.runtime.Composable
import ai.autocrab.android.MainViewModel
import ai.autocrab.android.ui.chat.ChatSheetContent

@Composable
fun ChatSheet(viewModel: MainViewModel) {
  ChatSheetContent(viewModel = viewModel)
}
